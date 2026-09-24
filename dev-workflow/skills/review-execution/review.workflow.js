export const meta = {
  name: 'review-execution',
  description: 'Dispatch the review-execution reviewer set (5 always-on lenses, optional implementation-reviewer, routed Apple reviewers) in one parallel batch, each with a StructuredOutput schema. Consolidates the structured returns into must-fix, nice-to-have, coverage, per-reviewer passthrough and a rendered markdown block.',
  phases: [
    { title: 'Dispatch Reviewers', detail: 'Build the args-driven reviewer list, dispatch every applicable reviewer in one parallel batch, consolidate the structured returns.' },
  ],
}

// Runtime characteristics (observed from the live Workflow runtime, not assumed):
//   * This script has NO filesystem access and NO Node.js built-ins. Routing
//     (route.py) and the SPANS_LAYERS judgment happen in the caller (SKILL.md
//     Step 1) BEFORE this script runs; `args.apple_reviewers` is passed through
//     verbatim — this script does not recompute Apple routing.
//   * This script can only be integration-tested through the Workflow runtime —
//     the harness in scripts/review_workflow.test.mjs is the syntax + logic check.
//   * `parallel(thunks)` runs `thunks.map(t => t())` through `Promise.all` with
//     NO per-thunk `.catch` in the runtime — a reviewer whose agent() throws (a
//     dead schema agent) or returns null (user-skip) must be caught INSIDE its
//     own thunk, or one dead reviewer takes the whole batch down.

phase('Dispatch Reviewers')

// The Workflow tool passes `args` through verbatim. A caller that JSON-stringifies
// the payload hands this script a string; every `args.x` deref then yields
// undefined and the run "succeeds" with nothing dispatched. Normalize, then
// reject any shape that cannot produce a dispatch list — before any agent() call,
// so a failed guard means zero agents ran and there is nothing to reconcile.
let input = args
if (typeof input === 'string') {
  try {
    input = JSON.parse(input)
  } catch (err) {
    throw new Error(
      `review-execution: args arrived as a string and is not valid JSON (${err.message}). ` +
      `Pass the payload as a JSON object, not a stringified one.`
    )
  }
  log('args arrived as a JSON string; parsed it. Callers should pass an object.')
}
if (!input || typeof input !== 'object' || Array.isArray(input)) {
  throw new Error(
    `review-execution: args must be a JSON object (got ${input === null ? 'null' : Array.isArray(input) ? 'array' : typeof input}).`
  )
}
if (!input.project_root || typeof input.project_root !== 'string') {
  throw new Error(
    `review-execution: args.project_root must be a non-empty string (got ${JSON.stringify(input.project_root)}; ` +
    `payload keys: ${Object.keys(input).join(', ') || 'none'}).`
  )
}
// Type-check every key the dispatch reads. A stringified boolean (`apple: "false"`)
// is truthy, so `!input.apple` / `!!input.spans_layers` would silently flip the
// Apple-coverage line and the feature-reviewer gate; a string `apple_reviewers`
// iterates characters. Reject the payload before any agent() call instead.
function guardFail(key, want) {
  throw new Error(`review-execution: args.${key} must be ${want} (got ${JSON.stringify(input[key])}).`)
}
for (const key of ['apple', 'apple_dev_installed', 'spans_layers']) {
  if (typeof input[key] !== 'boolean') guardFail(key, 'a boolean')
}
if (!Array.isArray(input.scope_files) || !input.scope_files.every(f => typeof f === 'string')) {
  guardFail('scope_files', 'an array of strings')
}
if (!Array.isArray(input.apple_reviewers) ||
    !input.apple_reviewers.every(e => e && typeof e === 'object' && !Array.isArray(e) && typeof e.agent === 'string')) {
  guardFail('apple_reviewers', 'an array of objects each with a string `agent` (route.py\'s apple_reviewers, verbatim)')
}
for (const key of ['plan_path', 'design_doc_path']) {
  if (input[key] !== null && typeof input[key] !== 'string') guardFail(key, 'a string or null')
}
if ('date' in input && typeof input.date !== 'string') guardFail('date', 'a string')

// Single source of which reviewer owes which section. Checked against the
// agents' **Return** blocks and run-phase's citations by scripts/test_contract.py.
// Between the two markers: ONLY the `const CONTRACT = {...}` JSON literal — no comments.
// CONTRACT:BEGIN
const CONTRACT = {
  "dev-workflow:implementation-reviewer": { "tests_line": "Tests:", "decisions_line": "Decisions:", "pre_existing_line": "Pre-existing:", "gaps_line": "Plan-vs-Code gaps:" },
  "apple-dev:ui-reviewer": { "part_c_human_verification": "### Part C: 人工验证清单" },
  "apple-dev:design-reviewer": { "part_a_red": "### Part A 🔴 项", "part_b_device_verification": "### Part B: 设备验证清单" },
  "apple-dev:feature-reviewer": { "part_c_device_verification": "### Part C: 设备验证清单" },
  "apple-dev:apple-reviewer": {}
}
// CONTRACT:END

// ---- Lens prompt bodies (copied verbatim from review-execution/SKILL.md Step 2) ----
// {project_root} is a literal placeholder substituted by withRoot() below — it is
// NOT JS interpolation, so the checklist text matches SKILL.md byte-for-byte apart
// from that one substitution.

const LENS_A_BODY = [
  "You are a code-correctness reviewer. Review uncommitted changes in {project_root} via `git diff` and `git diff --staged`. Focus only on logical correctness:",
  "- Off-by-one, null/undefined access, missing await/error handling",
  "- Incorrect conditionals, wrong operators",
  "- Type mismatches that escape the type-checker (any/unknown/casts)",
  "- Missing branches in exhaustive checks",
  "",
  "For each finding emit:",
  "`[Correctness/{severity:must-fix|nice-to-have}] {file}:{line} — {one-line description}`",
  "",
  "Do NOT comment on style, naming, or testing. Report-only; do not modify files.",
].join("\n")

const LENS_B_BODY = [
  "You are a test-coverage gap finder. Review uncommitted changes in {project_root}. For each new or modified function/method:",
  "- Is there a test that exercises it?",
  "- Are edge cases (empty input, error path, boundary) covered?",
  "",
  "For each gap emit:",
  "`[TestGap/{severity}] {file}:{symbol} — missing test for {scenario}`",
  "",
  "Do NOT write tests. Report-only.",
].join("\n")

const LENS_C_BODY = [
  "You are a breaking-change auditor. Review uncommitted changes in {project_root}:",
  "- Function signature changes (param added/removed, return type changed)",
  "- Type/interface changes (field removed, type changed)",
  "- Public marker changes (public → private, removed export)",
  "- Config key changes (renamed/removed)",
  "- Default value changes",
  "",
  "For each detection emit:",
  "`[Breaking/{severity}] {file}:{line} — {what changed} — {downstream impact}`",
  "",
  "Cross-reference: grep the codebase for callers of any removed/renamed symbols and list them.",
].join("\n")

const LENS_D_BODY = [
  "You are a root-cause-depth grader. For each fix-style change in the uncommitted diff, judge whether it addresses the root cause or is a surface-level patch:",
  "- Hardcoded vendor flag vs reading from config",
  "- Adding null check vs fixing the producer that returned null",
  "- Try/catch swallowing vs fixing the throwing code",
  "- Adding guardrail vs fixing the actual condition",
  "",
  "For each finding emit:",
  "`[Depth/{severity}] {file}:{line} — surface-level: {symptom} | root-cause would be: {what}`",
  "",
  "Skip enhancement / refactor / removal changes — only grade fixes.",
].join("\n")

const LENS_F_BODY = [
  "You are a security scanner. Scan ONLY the added/modified lines of the uncommitted diff for the four classes below. Report file:line and the matched text (redact the secret's tail: show at most the first 6 characters).",
  "",
  "1. Hardcoded secrets",
  "   - `sk-[a-zA-Z0-9]{20,}` (API keys), `AKIA[0-9A-Z]{16}` (AWS)",
  '   - `password\\s*[:=]\\s*"[^"]{8,}"`, `api[_-]?key\\s*[:=]\\s*"[^"]{8,}"`',
  "   - `-----BEGIN.*PRIVATE KEY-----`",
  '   Exclude test targets and obvious placeholders ("password123", "changeme", "xxx").',
  "2. Insecure transport",
  "   - `http://` in URL strings, excluding localhost / 127.0.0.1 / 0.0.0.0",
  "   - `NSAllowsArbitraryLoads` true in a plist",
  "   - custom `URLSession` / ServerTrust handling that skips validation or sets no TLS minimum",
  "3. Injection-shaped input handling",
  "   - string interpolation inside SQL (`\\(` near SELECT/INSERT/UPDATE/DELETE)",
  "   - `NSPredicate(format:` with `\\(` interpolation instead of `%@` arguments",
  "   - `WKWebView` loading a user-supplied URL with no scheme check",
  "4. Sensitive data at rest",
  "   - `UserDefaults` storing a token / password / key → should be Keychain",
  "   - (report only; do not judge an existing Keychain wrapper's quality)",
  "",
  "For each finding emit:",
  "`[Sec/{severity}] {file}:{line} — {class}: {what} | fix: {what to do instead}`",
  "",
  "Report nothing for classes with no hit. Do not speculate about code outside the diff.",
].join("\n")

function withRoot(text, projectRoot) {
  return text.replace('{project_root}', projectRoot)
}

function scopeLineFor(input) {
  const scopeFiles = Array.isArray(input.scope_files) ? input.scope_files : []
  if (scopeFiles.length > 0) {
    return [
      `Restrict every check to these files ONLY: ${scopeFiles.join(', ')}.`,
      "Ignore diff hunks in any other path, even if they look defective — they are outside this review's scope.",
    ].join('\n')
  }
  return 'Scope: the whole uncommitted diff.'
}

function buildLensEPrompt(input) {
  return [
    'Audit the implementation against the plan.',
    `Plan file: ${input.plan_path}`,
    `Design doc: ${input.design_doc_path || 'none'}`,
    `Project root: ${input.project_root}`,
  ].join('\n')
}

function buildApplePrompt(entry, input) {
  const projectRoot = input.project_root
  if (entry.agent === 'apple-dev:ui-reviewer') {
    return [
      'Review these SwiftUI files for UI + UX compliance:',
      ...(entry.files || []),
      '',
      `Project root: ${projectRoot}`,
    ].join('\n')
  }
  if (entry.agent === 'apple-dev:design-reviewer') {
    return [
      'Review these SwiftUI files for design quality (visual hierarchy, color, spacing):',
      ...(entry.files || []),
      '',
      `Project root: ${projectRoot}`,
    ].join('\n')
  }
  if (entry.agent === 'apple-dev:feature-reviewer') {
    return [
      `Feature spec(s): ${(entry.specs || []).join(', ') || 'none'}`,
      `Touched layers (caller's SPANS_LAYERS judgment): ${input.layers || 'unspecified'}`,
      `Project root: ${projectRoot}`,
    ].join('\n')
  }
  if (entry.agent === 'apple-dev:apple-reviewer') {
    return [
      'Review these non-Swift Apple-surface files:',
      ...(entry.files || []),
      '',
      `Project root: ${projectRoot}`,
    ].join('\n')
  }
  throw new Error(`review.workflow.js: unknown apple reviewer "${entry.agent}"`)
}

// ---- Schema builders ----

function findingsSchema(mapNote) {
  return {
    type: 'array',
    items: {
      type: 'object',
      additionalProperties: false,
      required: ['severity', 'file', 'line', 'text'],
      properties: {
        severity: { type: 'string', enum: ['must-fix', 'nice-to-have'], description: mapNote },
        file: { type: 'string', description: 'Repo-relative file path.' },
        line: { type: 'string', description: 'Line number or range, as a string.' },
        text: { type: 'string', description: 'One-line finding description.' },
      },
    },
  }
}

const LENS_SEVERITY_NOTE = 'must-fix or nice-to-have, mapped from your own severity marker in the checklist above.'
const NAMED_SEVERITY_NOTE = "must-fix or nice-to-have — map this reviewer's own marks: 🔴 → must-fix, 🟡/🟢 → nice-to-have."

function lensSchema() {
  return {
    type: 'object',
    additionalProperties: false,
    required: ['findings'],
    properties: {
      findings: findingsSchema(LENS_SEVERITY_NOTE),
    },
  }
}

function namedReviewerSchema(agentType) {
  const contract = CONTRACT[agentType] || {}
  const properties = {
    verdict: { type: 'string', description: 'Your verdict line, verbatim (e.g. "pass", "fail", "needs-attention").' },
    report_path: { type: 'string', description: 'Path to the report file you wrote, or empty string if you wrote none.' },
    findings: findingsSchema(NAMED_SEVERITY_NOTE),
  }
  const required = ['verdict', 'report_path', 'findings']
  const isAppleListReviewer = agentType.startsWith('apple-dev:') && agentType !== 'apple-dev:apple-reviewer'
  for (const [field, heading] of Object.entries(contract)) {
    properties[field] = {
      type: 'string',
      description: `Your "${heading}" content, verbatim, one item per line — do not repeat the heading itself. Empty string only if the section genuinely has zero items.`,
    }
    required.push(field)
    if (isAppleListReviewer) {
      const countField = `${field}_count`
      properties[countField] = {
        type: 'integer',
        description: `Number of items you put in "${field}" (count the non-empty lines).`,
      }
      required.push(countField)
    }
  }
  return { type: 'object', additionalProperties: false, required, properties }
}

// ---- Build the reviewer dispatch list ----
// Apple routing is NOT recomputed here — `input.apple_reviewers` (route.py's
// output, computed by the caller in SKILL.md Step 1) is passed through verbatim.
// The only judgment made in this script is the `when: "only if SPANS_LAYERS"` gate,
// because `input.spans_layers` (the model's judgment) arrives as a plain bool.

function buildReviewers(input) {
  const projectRoot = input.project_root
  const scope = scopeLineFor(input)
  const reviewers = []

  const lensDefs = [
    { letter: 'A', model: 'opus', body: LENS_A_BODY },
    { letter: 'B', model: 'sonnet', body: LENS_B_BODY },
    { letter: 'C', model: 'sonnet', body: LENS_C_BODY },
    { letter: 'D', model: 'opus', body: LENS_D_BODY },
    { letter: 'F', model: 'sonnet', body: LENS_F_BODY },
  ]
  for (const def of lensDefs) {
    reviewers.push({
      label: `lens:${def.letter}`,
      agentType: 'general-purpose',
      model: def.model,
      prompt: `${scope}\n\n${withRoot(def.body, projectRoot)}`,
      schema: lensSchema(),
    })
  }

  if (input.plan_path) {
    reviewers.push({
      label: 'lens:E',
      agentType: 'dev-workflow:implementation-reviewer',
      prompt: `${scope}\n\n${buildLensEPrompt(input)}`,
      schema: namedReviewerSchema('dev-workflow:implementation-reviewer'),
    })
  }

  for (const entry of (input.apple_reviewers || [])) {
    const fires = entry.when === 'only if SPANS_LAYERS' ? !!input.spans_layers : true
    if (!fires) continue
    const shortName = entry.agent.replace('apple-dev:', '')
    reviewers.push({
      label: `apple:${shortName}`,
      agentType: entry.agent,
      prompt: `${scope}\n\n${buildApplePrompt(entry, input)}`,
      schema: namedReviewerSchema(entry.agent),
    })
  }

  // A subagent's cwd is the session's, which need not be project_root. Observed
  // 2026-09-24: two lenses ran bare `git diff` and reviewed the session's repo
  // instead of the target. Pin every reviewer to the root explicitly.
  const pin = repoPinLine(projectRoot)
  for (const r of reviewers) r.prompt = `${pin}\n\n${r.prompt}`
  return reviewers
}

function repoPinLine(projectRoot) {
  return `Repository under review: ${projectRoot}. Run every git command as \`git -C ${projectRoot} …\` and resolve every relative path against it — your working directory may be a different repository.`
}

const reviewers = buildReviewers(input)

// One parallel batch. `parallel` in the live runtime runs `Promise.all` with NO
// per-thunk `.catch` — every thunk MUST swallow its own error/null result, or one
// dead reviewer rejects the whole batch and every other reviewer's result is lost.
const thunks = reviewers.map(r => async () => {
  try {
    const opts = { label: r.label, phase: 'Dispatch Reviewers', agentType: r.agentType, schema: r.schema }
    if (r.model) opts.model = r.model
    const value = await agent(r.prompt, opts)
    if (value == null) {
      return { ok: false, message: 'agent returned null (user-skip)' }
    }
    return { ok: true, value }
  } catch (err) {
    return { ok: false, message: err && err.message ? err.message : String(err) }
  }
})

const outcomes = await parallel(thunks)

// ---- Consolidate ----

// A named reviewer (Lens E, every apple-dev:*) is identified by agentType in
// `status` — the same key `passthrough` uses — so a caller can compare the two
// directly. The five plain lenses have no passthrough entry and are identified by label.
function statusKey(r) {
  return r.label.startsWith('lens:') && r.label !== 'lens:E' ? r.label : r.agentType
}

function appleCoverageLine(input, dispatchedApple) {
  if (!input.apple) return 'not applicable — non-Apple project'
  if (!input.apple_dev_installed) return 'apple-dev not installed — Apple-platform review coverage skipped for this run'
  if (dispatchedApple.length > 0) {
    return `dispatched: ${dispatchedApple.map(a => a.error === null ? a.agentType : `${a.agentType} (errored)`).join(', ')}`
  }
  return 'Apple project, apple-dev installed, no flag fired — checked: HAS_VIEW_MODIFIED, HAS_NEW_VIEW, HAS_FEATURE_SPEC, SPANS_LAYERS, HAS_APPLE_NONSWIFT'
}

function sortFindings(arr) {
  arr.sort((a, b) => {
    if (a.file !== b.file) return a.file < b.file ? -1 : 1
    if (a.lens !== b.lens) return a.lens < b.lens ? -1 : 1
    return 0
  })
  return arr
}

const must_fix = []
const nice_to_have = []
const passthrough = {}
const errored = []
const arrived = []
const missing = []
const contract_warnings = []
const lensCounts = {}
let lensEValue = input.plan_path ? 0 : 'skipped — no plan_path supplied'
// Every DISPATCHED Apple reviewer, errored or not — an errored one still counts as
// dispatched for the Apple coverage line and the `## Apple-Specific Findings` header.
const dispatchedApple = []
const dispatchedLabels = reviewers.map(r => r.label)

for (let i = 0; i < reviewers.length; i++) {
  const r = reviewers[i]
  const outcome = outcomes[i]
  const isPlainLens = r.label.startsWith('lens:') && r.label !== 'lens:E'
  const isApple = r.label.startsWith('apple:')

  if (!outcome.ok) {
    errored.push({ label: r.label, agentType: r.agentType, error: outcome.message })
    missing.push(statusKey(r))
    if (r.label === 'lens:E') lensEValue = 'errored'
    if (isPlainLens) lensCounts[r.label.slice('lens:'.length)] = 'errored'
    if (isApple) dispatchedApple.push({ agentType: r.agentType, error: outcome.message })
    continue
  }

  arrived.push(statusKey(r))
  const value = outcome.value
  const findings = Array.isArray(value.findings) ? value.findings : []
  for (const f of findings) {
    const bucket = f.severity === 'must-fix' ? must_fix : nice_to_have
    bucket.push({ lens: r.label, agentType: r.agentType, file: f.file, line: f.line, text: f.text })
  }

  if (isPlainLens) {
    lensCounts[r.label.slice('lens:'.length)] = findings.length
    continue
  }

  // Named reviewer (lens:E or apple:*) — has CONTRACT fields + verdict/report_path.
  if (r.label === 'lens:E') {
    lensEValue = findings.length
  } else {
    dispatchedApple.push({ agentType: r.agentType, error: null })
  }

  const contract = CONTRACT[r.agentType] || {}
  const fields = {}
  for (const field of Object.keys(contract)) {
    fields[field] = value[field] || ''
    const countField = `${field}_count`
    if (typeof value[countField] === 'number') {
      // Counts-only shape: the reviewer declared N items but the field does not hold N lines.
      const actualLines = String(value[field] || '').split('\n').map(l => l.trim()).filter(Boolean).length
      if (value[countField] !== actualLines) {
        contract_warnings.push({ agentType: r.agentType, field, kind: 'count_mismatch', declared_count: value[countField], actual_lines: actualLines })
      }
    } else if (String(value[field] || '').trim() === '') {
      // Empty-field shape: a field with no `_count` sibling (implementation-reviewer's
      // `Tests:` / `Decisions:` / `Pre-existing:` / `Plan-vs-Code gaps:` lines) always
      // carries a count sentence in a healthy return — empty means it was dropped.
      contract_warnings.push({ agentType: r.agentType, field, kind: 'empty' })
    }
  }
  passthrough[r.agentType] = { ...fields, verdict: value.verdict || '', report_path: value.report_path || '' }
}

sortFindings(must_fix)
sortFindings(nice_to_have)

// The explicit success signal. Callers gate on `status.ok === true`; they never
// infer success from the presence of `coverage` (it is always present).
const status = {
  ok: errored.length === 0 && arrived.length > 0,
  arrived,
  missing,
  errored,
}

const scopeFilesForCoverage = Array.isArray(input.scope_files) ? input.scope_files : []
const coverage = {
  lenses: { A: lensCounts.A ?? 0, B: lensCounts.B ?? 0, C: lensCounts.C ?? 0, D: lensCounts.D ?? 0, F: lensCounts.F ?? 0 },
  lens_e: lensEValue,
  scope: scopeFilesForCoverage.length > 0 ? `restricted to ${scopeFilesForCoverage.length} files from scope_files` : 'whole working tree',
  apple: appleCoverageLine(input, dispatchedApple),
  dispatched: dispatchedLabels,
  errored: errored.map(e => `${e.label}: ${e.error}`),
  contract_warnings,
}

function renderMarkdown(input, ctx) {
  // No Date here: the Workflow runtime throws on Date.now()/new Date() (it would
  // break resume). The caller passes `date` in args; without it the heading has none.
  const date = typeof input.date === 'string' ? input.date : ''
  const lines = []
  const errorFor = label => {
    const e = ctx.errored.find(x => x.label === label)
    return e ? e.error : ''
  }

  if (ctx.dispatchedApple.length > 0) {
    lines.push('## Apple-Specific Findings')
    lines.push('')
    for (const a of ctx.dispatchedApple) {
      if (a.error !== null) {
        lines.push(`- ${a.agentType}: errored — ${a.error}`)
        continue
      }
      lines.push(`- ${a.agentType} — verdict: ${ctx.passthrough[a.agentType].verdict}`)
    }
    lines.push('')
  }

  const lensLine = (letter, name) => {
    const v = ctx.coverage.lenses[letter]
    return v === 'errored'
      ? `- Lens ${letter} (${name}): errored — ${errorFor('lens:' + letter)}`
      : `- Lens ${letter} (${name}) returned: ${v} findings`
  }
  const lensE = ctx.coverage.lens_e
  const lensELine = typeof lensE === 'number'
    ? `${lensE} findings`
    : lensE === 'errored' ? `errored — ${errorFor('lens:E')}` : lensE
  const warningText = w => w.kind === 'empty'
    ? `${w.agentType}.${w.field} empty`
    : `${w.agentType}.${w.field} declared ${w.declared_count}, counted ${w.actual_lines}`

  lines.push(`## Review Findings — ${date}`)
  lines.push('')
  if (!ctx.status.ok) {
    lines.push(`⚠️ Review incomplete — status.ok is false: ${ctx.status.errored.length} of ${ctx.coverage.dispatched.length} dispatched reviewers errored (${ctx.status.missing.join(', ')}). Do not read this as a clean review.`)
    lines.push('')
  }
  lines.push(`### Must-fix (${ctx.must_fix.length})`)
  ctx.must_fix.forEach((f, i) => lines.push(`${i + 1}. [${f.lens}] ${f.file}:${f.line} — ${f.text}`))
  lines.push('')
  lines.push(`### Nice-to-have (${ctx.nice_to_have.length})`)
  ctx.nice_to_have.forEach((f, i) => lines.push(`${i + 1}. [${f.lens}] ${f.file}:${f.line} — ${f.text}`))
  lines.push('')
  lines.push('### Coverage notes')
  lines.push(lensLine('A', 'correctness'))
  lines.push(lensLine('B', 'test-coverage'))
  lines.push(lensLine('C', 'breaking'))
  lines.push(lensLine('D', 'depth'))
  lines.push(lensLine('F', 'secrets & transport'))
  lines.push(`- Lens E (plan-vs-code): ${lensELine}`)
  lines.push(`- Scope: ${ctx.coverage.scope}`)
  lines.push(`- Apple coverage: ${ctx.coverage.apple}`)
  lines.push(`- Any agent that errored: ${ctx.errored.length > 0 ? ctx.errored.map(e => `${e.label}: ${e.error}`).join('; ') : 'none'}`)
  lines.push(`- Contract warnings: ${ctx.coverage.contract_warnings.length > 0 ? ctx.coverage.contract_warnings.map(warningText).join('; ') : 'none'}`)
  lines.push('')
  lines.push('### Per-reviewer passthrough')
  for (const [agentType, fields] of Object.entries(ctx.passthrough)) {
    lines.push('')
    lines.push(`**${agentType}**`)
    lines.push(`Verdict: ${fields.verdict}`)
    if (fields.report_path) lines.push(`Report: ${fields.report_path}`)
    const contract = CONTRACT[agentType] || {}
    for (const [field, heading] of Object.entries(contract)) {
      if (heading.startsWith('###')) {
        lines.push('')
        lines.push(heading)
        lines.push(fields[field] || '')
      } else {
        lines.push(`${heading} ${fields[field] || ''}`)
      }
    }
  }

  return lines.join('\n')
}

const rendered = renderMarkdown(input, { must_fix, nice_to_have, coverage, passthrough, errored, status, dispatchedApple })

return { must_fix, nice_to_have, coverage, passthrough, status, rendered }
