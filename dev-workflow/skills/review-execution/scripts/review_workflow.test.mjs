import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const SCRIPT_PATH = fileURLToPath(new URL('../review.workflow.js', import.meta.url))

// ---- Harness: strip `export const meta = {...}` (string-aware brace matching),
// then run the remaining body as the same kind of AsyncFunction the live Workflow
// runtime constructs. Reads the file fresh on every call so a syntax error in the
// script surfaces as that specific test's failure, not a module-load failure that
// hides every other case (prototyped against execute-plan.workflow.js).

function stripMetaBlock(text) {
  const metaStart = text.indexOf('export const meta')
  if (metaStart === -1) {
    throw new Error('review_workflow.test.mjs: "export const meta" not found in review.workflow.js')
  }
  const braceStart = text.indexOf('{', metaStart)
  if (braceStart === -1) {
    throw new Error('review_workflow.test.mjs: no "{" found after "export const meta"')
  }
  let depth = 0
  let inString = null
  let end = -1
  for (let i = braceStart; i < text.length; i++) {
    const ch = text[i]
    if (inString) {
      if (ch === '\\') { i++; continue }
      if (ch === inString) inString = null
      continue
    }
    if (ch === "'" || ch === '"' || ch === '`') { inString = ch; continue }
    if (ch === '{') depth++
    else if (ch === '}') {
      depth--
      if (depth === 0) { end = i; break }
    }
  }
  if (end === -1) {
    throw new Error('review_workflow.test.mjs: unbalanced braces while scanning the "meta" block')
  }
  return text.slice(0, metaStart) + text.slice(end + 1)
}

function loadScriptBody() {
  const text = readFileSync(SCRIPT_PATH, 'utf8')
  return stripMetaBlock(text)
}

function buildRunner() {
  const body = loadScriptBody()
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
  // Mirror the live runtime: Date / Math.random throw there (they break resume).
  // Without this shim a `new Date()` in the script passes here and dies in production.
  const runner = new AsyncFunction('Date', 'Math', 'agent', 'parallel', 'pipeline', 'phase', 'log', 'args', body)
  const ThrowingDate = function () {
    throw new Error('Date.now() / new Date() are unavailable in workflow scripts (breaks resume).')
  }
  ThrowingDate.now = ThrowingDate
  const ShimMath = Object.assign(Object.create(Math), { random: () => { throw new Error('Math.random() unavailable in workflow scripts') } })
  return (...rest) => runner(ThrowingDate, ShimMath, ...rest)
}

// ---- Stubs ----

function makeAgentStub({ dead = new Set(), nullLabels = new Set(), canned = {} } = {}) {
  const calls = []
  const agentFn = async (prompt, opts) => {
    calls.push({ prompt, opts })
    if (dead.has(opts.label)) {
      throw new Error('agent({schema}): subagent completed without calling StructuredOutput (after in-conversation nudge)')
    }
    if (nullLabels.has(opts.label)) {
      return null
    }
    if (opts.label in canned) {
      const c = canned[opts.label]
      return typeof c === 'function' ? c(opts) : c
    }
    return { findings: [], verdict: 'pass', report_path: '' }
  }
  agentFn.calls = calls
  return agentFn
}

// The real runtime's `parallel` has NO per-thunk `.catch` — a missing try/catch
// inside a thunk must make Promise.all reject, and therefore make the test fail.
function parallelStub(thunks) {
  return Promise.all(thunks.map(t => t()))
}

function phaseStub() {}
function logStub() {}
function pipelineStub() {}

function baseArgs(overrides = {}) {
  return {
    project_root: '/tmp/proj',
    scope_files: [],
    plan_path: null,
    design_doc_path: null,
    mode: 'advisory',
    apple: false,
    apple_dev_installed: false,
    apple_reviewers: [],
    spans_layers: false,
    layers: '',
    date: '2026-01-02',
    ...overrides,
  }
}

// ---- Tests ----

test('CONTRACT block between markers parses as JSON (regression guard for scripts/test_contract.py)', () => {
  const text = readFileSync(SCRIPT_PATH, 'utf8')
  const begin = text.indexOf('// CONTRACT:BEGIN')
  const end = text.indexOf('// CONTRACT:END')
  assert.ok(begin !== -1 && end !== -1 && end > begin, 'CONTRACT:BEGIN/END markers must both be present, in order')
  const slice = text.slice(begin, end)
  const jsonText = slice
    .replace('// CONTRACT:BEGIN', '')
    .replace(/^\s*const CONTRACT\s*=\s*/m, '')
    .trim()
  const parsed = JSON.parse(jsonText)
  assert.ok('dev-workflow:implementation-reviewer' in parsed)
  assert.ok('apple-dev:ui-reviewer' in parsed)
  assert.ok('apple-dev:design-reviewer' in parsed)
  assert.ok('apple-dev:feature-reviewer' in parsed)
  assert.ok('apple-dev:apple-reviewer' in parsed)
})

test('non-Apple, no plan_path: dispatches exactly the 5 lenses with correct agentType/model and the whole-diff scope line', async () => {
  const agent = makeAgentStub()
  const run = buildRunner()
  const result = await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs())

  const labels = agent.calls.map(c => c.opts.label)
  assert.deepStrictEqual(labels, ['lens:A', 'lens:B', 'lens:C', 'lens:D', 'lens:F'])
  // the heading carries args.date; the script never calls Date itself
  assert.ok(result.rendered.includes('2026-01-02'), 'rendered heading carries args.date')

  for (const call of agent.calls) {
    assert.strictEqual(call.opts.agentType, 'general-purpose', `${call.opts.label} must use agentType general-purpose`)
    const [pin, , scopeLine] = call.prompt.split('\n')
    assert.ok(pin.startsWith(`Repository under review: ${baseArgs().project_root}.`), `${call.opts.label} prompt must open with the repo pin line`)
    assert.ok(pin.includes(`git -C ${baseArgs().project_root}`), `${call.opts.label} pin line must name git -C <root>`)
    assert.ok(scopeLine.startsWith('Scope: the whole uncommitted diff.'), `${call.opts.label} prompt must carry the whole-diff scope line right after the pin`)
  }

  const modelByLabel = Object.fromEntries(agent.calls.map(c => [c.opts.label, c.opts.model]))
  assert.strictEqual(modelByLabel['lens:A'], 'opus')
  assert.strictEqual(modelByLabel['lens:D'], 'opus')
  assert.strictEqual(modelByLabel['lens:B'], 'sonnet')
  assert.strictEqual(modelByLabel['lens:C'], 'sonnet')
  assert.strictEqual(modelByLabel['lens:F'], 'sonnet')

  assert.strictEqual(result.coverage.dispatched.length, 5)
})

test('scope_files supplied: every prompt starts with the restricted-scope form', async () => {
  const agent = makeAgentStub()
  const run = buildRunner()
  await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs({ scope_files: ['a.ts', 'b.ts'] }))

  for (const call of agent.calls) {
    assert.ok(
      call.prompt.split('\n')[2].startsWith('Restrict every check to these files ONLY: a.ts, b.ts.'),
      `${call.opts.label} prompt must start with the restricted-scope line`
    )
  }
})

test('plan_path supplied: dispatches a 6th reviewer (implementation-reviewer) whose schema requires every CONTRACT field, with no model key', async () => {
  const agent = makeAgentStub()
  const run = buildRunner()
  await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs({ plan_path: 'docs/plan.md' }))

  assert.strictEqual(agent.calls.length, 6)
  const lensE = agent.calls.find(c => c.opts.label === 'lens:E')
  assert.ok(lensE, 'lens:E must have been dispatched')
  assert.strictEqual(lensE.opts.agentType, 'dev-workflow:implementation-reviewer')
  assert.ok(!('model' in lensE.opts), 'named agent dispatch must not set a model key')
  for (const field of ['tests_line', 'decisions_line', 'pre_existing_line', 'gaps_line']) {
    assert.ok(lensE.opts.schema.required.includes(field), `schema.required must include ${field}`)
  }
})

test('apple_reviewers is passed through verbatim: when-gating on spans_layers, feature-reviewer carries its full specs list', async () => {
  const appleReviewers = [
    { agent: 'apple-dev:ui-reviewer', files: ['Views/AView.swift'] },
    { agent: 'apple-dev:feature-reviewer', when: 'only if SPANS_LAYERS', specs: ['docs/05-features/x.md'] },
  ]

  const agentNoSpan = makeAgentStub()
  const runNoSpan = buildRunner()
  await runNoSpan(agentNoSpan, parallelStub, pipelineStub, phaseStub, logStub, baseArgs({
    apple: true, apple_dev_installed: true, apple_reviewers: appleReviewers, spans_layers: false,
  }))
  let labels = agentNoSpan.calls.map(c => c.opts.label)
  assert.ok(labels.includes('apple:ui-reviewer'))
  assert.ok(!labels.includes('apple:feature-reviewer'), 'feature-reviewer with when:"only if SPANS_LAYERS" must not fire when spans_layers is false')

  const agentSpan = makeAgentStub()
  const runSpan = buildRunner()
  await runSpan(agentSpan, parallelStub, pipelineStub, phaseStub, logStub, baseArgs({
    apple: true, apple_dev_installed: true, apple_reviewers: appleReviewers, spans_layers: true,
  }))
  labels = agentSpan.calls.map(c => c.opts.label)
  assert.ok(labels.includes('apple:feature-reviewer'), 'feature-reviewer must fire when spans_layers is true')
  const featureCall = agentSpan.calls.find(c => c.opts.label === 'apple:feature-reviewer')
  assert.ok(featureCall.prompt.includes('docs/05-features/x.md'), 'feature-reviewer prompt must carry the full specs list')
})

test('empty apple_reviewers list: no Apple dispatch', async () => {
  const agent = makeAgentStub()
  const run = buildRunner()
  await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs({ apple_reviewers: [] }))
  const labels = agent.calls.map(c => c.opts.label)
  assert.ok(!labels.some(l => l.startsWith('apple:')))
})

test('Apple reviewer schemas require their CONTRACT fields plus a _count sibling; a wrong declared count is caught', async () => {
  const appleReviewers = [
    { agent: 'apple-dev:ui-reviewer', files: ['A View.swift'] },
    { agent: 'apple-dev:design-reviewer', files: ['B View.swift'] },
    { agent: 'apple-dev:feature-reviewer', when: 'always', specs: ['docs/05-features/x.md'] },
  ]
  const canned = {
    'apple:ui-reviewer': {
      verdict: 'pass', report_path: '.claude/reviews/ui.md', findings: [],
      part_c_human_verification: '- [ ] item one\n- [ ] item two',
      part_c_human_verification_count: 5, // wrong on purpose — actual is 2
    },
    'apple:design-reviewer': {
      verdict: 'pass', report_path: '.claude/reviews/design.md', findings: [],
      part_a_red: '', part_a_red_count: 0,
      part_b_device_verification: '- [ ] check', part_b_device_verification_count: 1,
    },
    'apple:feature-reviewer': {
      verdict: 'pass', report_path: '.claude/reviews/feature.md', findings: [],
      part_c_device_verification: '- [ ] a\n- [ ] b\n- [ ] c', part_c_device_verification_count: 3,
    },
  }
  const agent = makeAgentStub({ canned })
  const run = buildRunner()
  const result = await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs({
    apple: true, apple_dev_installed: true, apple_reviewers: appleReviewers, spans_layers: false,
  }))

  const uiCall = agent.calls.find(c => c.opts.label === 'apple:ui-reviewer')
  assert.ok(uiCall.opts.schema.required.includes('part_c_human_verification'))
  assert.ok(uiCall.opts.schema.required.includes('part_c_human_verification_count'))
  assert.strictEqual(uiCall.opts.schema.properties.part_c_human_verification_count.type, 'integer')

  const designCall = agent.calls.find(c => c.opts.label === 'apple:design-reviewer')
  for (const f of ['part_a_red', 'part_b_device_verification']) {
    assert.ok(designCall.opts.schema.required.includes(f))
    assert.ok(designCall.opts.schema.required.includes(`${f}_count`))
  }

  const featureCall = agent.calls.find(c => c.opts.label === 'apple:feature-reviewer')
  assert.ok(featureCall.opts.schema.required.includes('part_c_device_verification'))
  assert.ok(featureCall.opts.schema.required.includes('part_c_device_verification_count'))

  assert.ok(
    result.coverage.contract_warnings.some(w => w.agentType === 'apple-dev:ui-reviewer' && w.field === 'part_c_human_verification'),
    'a declared count that disagrees with the actual line count must be recorded'
  )
  assert.ok(
    result.rendered.split('\n').includes('- Contract warnings: apple-dev:ui-reviewer.part_c_human_verification declared 5, counted 2'),
    'a non-empty contract_warnings list must be rendered on the Contract warnings line'
  )
  assert.ok(!result.coverage.contract_warnings.some(w => w.agentType === 'apple-dev:design-reviewer'))
  assert.ok(!result.coverage.contract_warnings.some(w => w.agentType === 'apple-dev:feature-reviewer'))
})

test('consolidation: must-fix and nice-to-have findings are bucketed and sorted by file then lens', async () => {
  const canned = {
    'lens:A': { findings: [
      { severity: 'must-fix', file: 'z.ts', line: '1', text: 'must A z' },
      { severity: 'nice-to-have', file: 'a.ts', line: '2', text: 'nice A a' },
    ] },
    'lens:B': { findings: [
      { severity: 'must-fix', file: 'a.ts', line: '3', text: 'must B a' },
    ] },
  }
  const agent = makeAgentStub({ canned })
  const run = buildRunner()
  const result = await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs())

  assert.strictEqual(result.must_fix.length, 2)
  assert.strictEqual(result.must_fix[0].file, 'a.ts', 'must-fix should be sorted by file first')
  assert.strictEqual(result.must_fix[1].file, 'z.ts')
  assert.strictEqual(result.nice_to_have.length, 1)
  assert.strictEqual(result.nice_to_have[0].file, 'a.ts')
})

test('a dead (throwing) reviewer and a null (user-skip) reviewer both land in errored, without taking down the other reviewers', async () => {
  const canned = { 'lens:C': { findings: [{ severity: 'must-fix', file: 'x.ts', line: '1', text: 'ok' }] } }
  const agent = makeAgentStub({ dead: new Set(['lens:A']), nullLabels: new Set(['lens:B']), canned })
  const run = buildRunner()
  const result = await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs())

  assert.strictEqual(result.status.errored.length, 2)
  const erroredLabels = result.status.errored.map(e => e.label)
  assert.ok(erroredLabels.includes('lens:A'))
  assert.ok(erroredLabels.includes('lens:B'))
  assert.ok(result.status.errored.find(e => e.label === 'lens:A').error.includes('StructuredOutput'))
  assert.ok(result.status.errored.find(e => e.label === 'lens:B').error.includes('user-skip'))

  assert.deepStrictEqual(result.passthrough, {}, 'plain lenses never produce a passthrough entry')
  assert.ok(result.coverage.dispatched.includes('lens:A'))
  assert.ok(result.coverage.dispatched.includes('lens:B'))
  assert.ok(result.coverage.dispatched.includes('lens:C'), 'a sibling reviewer must still be dispatched and arrive despite lens:A/B dying')
  assert.strictEqual(result.must_fix.length, 1, 'lens:C, unaffected by its dead siblings, must still contribute its finding')

  assert.ok(result.rendered.includes('Any agent that errored:'))
  assert.ok(result.rendered.includes('lens:A'))
})

test('rendered contains the required headings; non-Apple run has no Apple header and states "not applicable"', async () => {
  const agent = makeAgentStub()
  const run = buildRunner()
  const result = await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs())

  for (const heading of ['### Must-fix (0)', '### Nice-to-have (0)', '### Coverage notes', '### Per-reviewer passthrough']) {
    assert.ok(result.rendered.includes(heading), `rendered must contain "${heading}"`)
  }
  assert.ok(!result.rendered.startsWith('## Apple-Specific Findings'), 'non-Apple run must not get the Apple header')
  assert.ok(result.rendered.includes('Apple coverage: not applicable — non-Apple project'))
})

test('rendered starts with ## Apple-Specific Findings when an Apple reviewer ran, and reproduces the verbatim original heading under passthrough', async () => {
  const appleReviewers = [{ agent: 'apple-dev:ui-reviewer', files: ['A View.swift'] }]
  const canned = {
    'apple:ui-reviewer': {
      verdict: 'pass', report_path: '.claude/reviews/ui.md', findings: [],
      part_c_human_verification: '- [ ] item', part_c_human_verification_count: 1,
    },
  }
  const agent = makeAgentStub({ canned })
  const run = buildRunner()
  const result = await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs({
    apple: true, apple_dev_installed: true, apple_reviewers: appleReviewers, spans_layers: false,
  }))

  assert.ok(result.rendered.startsWith('## Apple-Specific Findings'))
  assert.ok(result.rendered.includes('### Part C: 人工验证清单'))
  assert.ok(result.rendered.includes('- [ ] item'))
  assert.ok('apple-dev:ui-reviewer' in result.passthrough)
  assert.strictEqual(result.passthrough['apple-dev:ui-reviewer'].part_c_human_verification, '- [ ] item')
})

test('Apple coverage line: "no flag fired" variant when apple project + installed but nothing dispatched', async () => {
  const appleReviewers = [{ agent: 'apple-dev:feature-reviewer', when: 'only if SPANS_LAYERS', specs: [] }]
  const agent = makeAgentStub()
  const run = buildRunner()
  const result = await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs({
    apple: true, apple_dev_installed: true, apple_reviewers: appleReviewers, spans_layers: false,
  }))
  assert.ok(result.rendered.includes(
    'Apple project, apple-dev installed, no flag fired — checked: HAS_VIEW_MODIFIED, HAS_NEW_VIEW, HAS_FEATURE_SPEC, SPANS_LAYERS, HAS_APPLE_NONSWIFT'
  ))
})

test('Apple coverage line: "apple-dev not installed" variant', async () => {
  const agent = makeAgentStub()
  const run = buildRunner()
  const result = await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs({
    apple: true, apple_dev_installed: false, apple_reviewers: [],
  }))
  assert.ok(result.rendered.includes('Apple coverage: apple-dev not installed'))
})

test('args passed as a JSON string is parsed (and logged)', async () => {
  const agent = makeAgentStub()
  const run = buildRunner()
  const logs = []
  await run(agent, parallelStub, pipelineStub, phaseStub, (msg) => logs.push(msg), JSON.stringify(baseArgs()))
  assert.strictEqual(agent.calls.length, 5)
  assert.ok(logs.length > 0, 'a string args payload must be logged')
})

test('non-object args, or args missing project_root, throws before any agent dispatch', async () => {
  const agent1 = makeAgentStub()
  const run1 = buildRunner()
  await assert.rejects(run1(agent1, parallelStub, pipelineStub, phaseStub, logStub, null))
  assert.strictEqual(agent1.calls.length, 0)

  const agent2 = makeAgentStub()
  const run2 = buildRunner()
  await assert.rejects(run2(agent2, parallelStub, pipelineStub, phaseStub, logStub, { scope_files: [] }))
  assert.strictEqual(agent2.calls.length, 0)
})

// ---- status: explicit success signal (must-fix 1/2) ----

const FILLED_LENS_E = {
  verdict: 'pass', report_path: '.claude/reviews/impl.md', findings: [],
  tests_line: '3 required, 3 exist, 3 covered, shell: 0',
  decisions_line: '0 blocking, 0 recommended',
  pre_existing_line: '0 issues found',
  gaps_line: '0 total (0 reported C>=80, 0 filtered C<80)',
}
const FILLED_APPLE = {
  'apple:ui-reviewer': {
    verdict: 'pass', report_path: '.claude/reviews/ui.md', findings: [],
    part_c_human_verification: '- [ ] tap works', part_c_human_verification_count: 1,
  },
  'apple:design-reviewer': {
    verdict: 'pass', report_path: '.claude/reviews/design.md', findings: [],
    part_a_red: '', part_a_red_count: 0,
    part_b_device_verification: '- [ ] check', part_b_device_verification_count: 1,
  },
  'apple:feature-reviewer': {
    verdict: 'pass', report_path: '.claude/reviews/feature.md', findings: [],
    part_c_device_verification: '- [ ] a', part_c_device_verification_count: 1,
  },
}
const THREE_APPLE = [
  { agent: 'apple-dev:ui-reviewer', files: ['AView.swift'] },
  { agent: 'apple-dev:design-reviewer', files: ['BView.swift'] },
  { agent: 'apple-dev:feature-reviewer', when: 'always', specs: ['docs/05-features/x.md'] },
]

test('healthy run: status.ok true, nothing missing, no contract warnings, every passthrough key arrived', async () => {
  const agent = makeAgentStub({ canned: { 'lens:E': FILLED_LENS_E, ...FILLED_APPLE } })
  const run = buildRunner()
  const result = await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs({
    plan_path: 'docs/plan.md', apple: true, apple_dev_installed: true, apple_reviewers: THREE_APPLE,
  }))

  assert.strictEqual(result.status.ok, true)
  assert.deepStrictEqual(result.status.missing, [])
  assert.deepStrictEqual(result.status.errored, [])
  assert.deepStrictEqual(result.coverage.contract_warnings, [], 'a healthy run must not produce contract warnings')
  assert.deepStrictEqual(result.status.arrived, [
    'lens:A', 'lens:B', 'lens:C', 'lens:D', 'lens:F',
    'dev-workflow:implementation-reviewer',
    'apple-dev:ui-reviewer', 'apple-dev:design-reviewer', 'apple-dev:feature-reviewer',
  ])
  for (const key of Object.keys(result.passthrough)) {
    assert.ok(result.status.arrived.includes(key), `passthrough key ${key} must appear in status.arrived`)
  }
  assert.ok(!('errored' in result), 'top-level errored is replaced by status.errored')
  assert.ok(!result.rendered.includes('Review incomplete'), 'a healthy run carries no failure banner')
})

test('errored lens: status.ok false, coverage reads "errored", rendered prints the error instead of "returned: 0 findings"', async () => {
  const agent = makeAgentStub({ dead: new Set(['lens:A']) })
  const run = buildRunner()
  const result = await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs())

  assert.strictEqual(result.status.ok, false)
  assert.deepStrictEqual(result.status.missing, ['lens:A'])
  assert.deepStrictEqual(result.status.errored.map(e => [e.label, e.agentType]), [['lens:A', 'general-purpose']])
  assert.strictEqual(result.coverage.lenses.A, 'errored')
  assert.strictEqual(result.coverage.lenses.B, 0)
  const lines = result.rendered.split('\n')
  assert.ok(
    lines.includes('- Lens A (correctness): errored — agent({schema}): subagent completed without calling StructuredOutput (after in-conversation nudge)'),
    'errored lens must render its error message'
  )
  assert.ok(!result.rendered.includes('Lens A (correctness) returned'), 'an errored lens must not render as "returned: N findings"')
  assert.ok(result.rendered.includes('⚠️ Review incomplete — status.ok is false: 1 of 5 dispatched reviewers errored (lens:A).'))
})

test('null Lens E: status.missing names the agentType, lens_e reads errored with the message', async () => {
  const agent = makeAgentStub({ nullLabels: new Set(['lens:E']) })
  const run = buildRunner()
  const result = await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs({ plan_path: 'docs/plan.md' }))

  assert.strictEqual(result.status.ok, false)
  assert.deepStrictEqual(result.status.missing, ['dev-workflow:implementation-reviewer'])
  assert.strictEqual(result.coverage.lens_e, 'errored')
  assert.ok(result.rendered.split('\n').includes('- Lens E (plan-vs-code): errored — agent returned null (user-skip)'))
})

test('every reviewer errored: nothing arrived, status.ok false', async () => {
  const agent = makeAgentStub({ dead: new Set(['lens:A', 'lens:B', 'lens:C', 'lens:D', 'lens:F']) })
  const run = buildRunner()
  const result = await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs())
  assert.deepStrictEqual(result.status.arrived, [])
  assert.strictEqual(result.status.ok, false)
})

test('errored Apple reviewer still counts as dispatched: Apple line marks it errored, header present, status.ok false', async () => {
  const appleReviewers = [
    { agent: 'apple-dev:ui-reviewer', files: ['AView.swift'] },
    { agent: 'apple-dev:design-reviewer', files: ['BView.swift'] },
  ]
  const agent = makeAgentStub({ dead: new Set(['apple:ui-reviewer']), canned: FILLED_APPLE })
  const run = buildRunner()
  const result = await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs({
    apple: true, apple_dev_installed: true, apple_reviewers: appleReviewers,
  }))

  assert.strictEqual(result.status.ok, false)
  assert.deepStrictEqual(result.status.missing, ['apple-dev:ui-reviewer'])
  assert.ok(result.status.arrived.includes('apple-dev:design-reviewer'))
  assert.strictEqual(result.coverage.apple, 'dispatched: apple-dev:ui-reviewer (errored), apple-dev:design-reviewer')
  assert.ok(result.rendered.startsWith('## Apple-Specific Findings'), 'an errored Apple reviewer still gets the Apple header')
  const lines = result.rendered.split('\n')
  assert.ok(lines.some(l => l.startsWith('- apple-dev:ui-reviewer: errored — ') && l.includes('StructuredOutput')))
  assert.ok(lines.includes('- apple-dev:design-reviewer — verdict: pass'))
})

// ---- entry guard type validation (must-fix 3) ----

async function assertGuardRejects(overrides, pattern) {
  const agent = makeAgentStub()
  const run = buildRunner()
  await assert.rejects(run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs(overrides)), pattern)
  assert.strictEqual(agent.calls.length, 0, `guard must throw before any dispatch for ${JSON.stringify(overrides)}`)
}

test('entry guard: stringified booleans throw before any dispatch', async () => {
  await assertGuardRejects({ apple: 'false' }, /args\.apple must be a boolean/)
  await assertGuardRejects({ apple_dev_installed: 'true' }, /args\.apple_dev_installed must be a boolean/)
  await assertGuardRejects({ spans_layers: 'false' }, /args\.spans_layers must be a boolean/)
  await assertGuardRejects({ spans_layers: undefined }, /args\.spans_layers must be a boolean/)
})

test('entry guard: scope_files and apple_reviewers shapes', async () => {
  await assertGuardRejects({ scope_files: 'a.ts' }, /args\.scope_files must be an array of strings/)
  await assertGuardRejects({ scope_files: ['a.ts', 3] }, /args\.scope_files must be an array of strings/)
  await assertGuardRejects({ apple_reviewers: '[{"agent":"apple-dev:ui-reviewer"}]' }, /args\.apple_reviewers must be an array of objects/)
  await assertGuardRejects({ apple_reviewers: [{ files: ['A.swift'] }] }, /args\.apple_reviewers must be an array of objects/)
  await assertGuardRejects({ apple_reviewers: ['apple-dev:ui-reviewer'] }, /args\.apple_reviewers must be an array of objects/)
})

test('entry guard: plan_path / design_doc_path string|null, date string when present', async () => {
  await assertGuardRejects({ plan_path: 5 }, /args\.plan_path must be a string or null/)
  await assertGuardRejects({ plan_path: undefined }, /args\.plan_path must be a string or null/)
  await assertGuardRejects({ design_doc_path: false }, /args\.design_doc_path must be a string or null/)
  await assertGuardRejects({ date: 20260102 }, /args\.date must be a string/)

  // absent date is allowed; the heading just carries no date
  const agent = makeAgentStub()
  const run = buildRunner()
  const a = baseArgs()
  delete a.date
  await run(agent, parallelStub, pipelineStub, phaseStub, logStub, a)
  assert.strictEqual(agent.calls.length, 5)
})

// ---- coverage for the remaining branches (item 6) ----

test('apple-reviewer branch: non-Swift prompt, schema carries only the common fields (empty CONTRACT)', async () => {
  const agent = makeAgentStub()
  const run = buildRunner()
  await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs({
    apple: true, apple_dev_installed: true,
    apple_reviewers: [{ agent: 'apple-dev:apple-reviewer', files: ['App/Info.plist', 'Package.swift'] }],
  }))
  const call = agent.calls.find(c => c.opts.label === 'apple:apple-reviewer')
  assert.ok(call, 'apple-reviewer must be dispatched')
  assert.ok(call.prompt.includes('Review these non-Swift Apple-surface files:\nApp/Info.plist\nPackage.swift\n'))
  assert.deepStrictEqual(call.opts.schema.required, ['verdict', 'report_path', 'findings'])
  assert.ok(!('model' in call.opts))
})

test('unknown apple agent throws loudly before any dispatch', async () => {
  await assertGuardRejects(
    { apple: true, apple_dev_installed: true, apple_reviewers: [{ agent: 'apple-dev:bogus-reviewer', files: [] }] },
    /unknown apple reviewer "apple-dev:bogus-reviewer"/
  )
})

test('exact Apple coverage line for a healthy multi-reviewer run', async () => {
  const agent = makeAgentStub({ canned: FILLED_APPLE })
  const run = buildRunner()
  const result = await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs({
    apple: true, apple_dev_installed: true,
    apple_reviewers: [{ agent: 'apple-dev:ui-reviewer', files: ['AView.swift'] }, { agent: 'apple-dev:apple-reviewer', files: ['Info.plist'] }],
  }))
  assert.ok(result.rendered.split('\n').includes('- Apple coverage: dispatched: apple-dev:ui-reviewer, apple-dev:apple-reviewer'))
})

test('sortFindings: same file sorts by lens label, not by arrival order (lens:E arrives after lens:F)', async () => {
  const canned = {
    'lens:F': { findings: [{ severity: 'must-fix', file: 'a.ts', line: '1', text: 'F' }] },
    'lens:E': { ...FILLED_LENS_E, findings: [{ severity: 'must-fix', file: 'a.ts', line: '2', text: 'E' }] },
  }
  const agent = makeAgentStub({ canned })
  const run = buildRunner()
  const result = await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs({ plan_path: 'docs/plan.md' }))
  assert.deepStrictEqual(result.must_fix.map(f => f.lens), ['lens:E', 'lens:F'])
})

test('Lens E prompt: design_doc_path null renders "Design doc: none"', async () => {
  const agent = makeAgentStub()
  const run = buildRunner()
  await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs({ plan_path: 'docs/plan.md', design_doc_path: null }))
  const call = agent.calls.find(c => c.opts.label === 'lens:E')
  assert.ok(call.prompt.split('\n').includes('Design doc: none'))
})

test('empty-field shape: Lens E with an empty required line is a contract warning; filled lines are not', async () => {
  const agent = makeAgentStub({ canned: { 'lens:E': { ...FILLED_LENS_E, tests_line: '' } } })
  const run = buildRunner()
  const result = await run(agent, parallelStub, pipelineStub, phaseStub, logStub, baseArgs({ plan_path: 'docs/plan.md' }))
  assert.deepStrictEqual(
    result.coverage.contract_warnings,
    [{ agentType: 'dev-workflow:implementation-reviewer', field: 'tests_line', kind: 'empty' }]
  )
  assert.ok(result.rendered.split('\n').includes('- Contract warnings: dev-workflow:implementation-reviewer.tests_line empty'))
})
