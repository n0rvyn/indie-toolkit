# Eval Rules for Plugins

Reference doc consumed by `plugin-master` (Create / Iterate / Package routes) and `plugin-reviewer` (Dimension 9.2). This file is the canonical home of the eval layout rule; indie-toolkit's `docs/99-references/eval-format-spec.md` points here. Evidence and verification log: indie-toolkit `docs/99-references/claude-plugin-eval.md`.

## Two tools, two jobs

| Tool | Owns | Runs in |
|---|---|---|
| `claude plugin eval` (Claude Code ≥ 2.1.269) | Behavior, regression, with-vs-without delta (Δ) | An isolated `claude -p` child with only the plugin under test loaded — no user settings, hooks, `CLAUDE.md`, memory, or other plugins |
| skill-creator `run_loop` / `run_eval.py` | Description optimization; trigger competition against everything else installed | Your real environment (inherited env, project root, all installed plugins) |

Neither replaces the other. `eval.md` is a spec: nothing executes its Output Assertions.

## Layout (one eval dir per plugin, grouped by skill)

```text
<plugin>/
├── skills/<skill>/eval.md            # always exists: pointer, mixed, or spec form
└── evals/
    ├── <skill>/                      # always exists, one per skill
    │   ├── <case>/                   # one case = one user prompt, named after the prompt (kebab-case)
    │   │   ├── prompt.md
    │   │   └── graders/*.md
    │   └── NOTE.md                   # only when the skill has no cases
    ├── _hooks/<hook>/<case>/         # optional: hook cases, graded by effect
    └── results/                      # written by each run; gitignored
```

- `claude plugin eval init` writes flat `evals/<case>/`. Move each generated case into `evals/<skill>/` afterwards.
- Every case sets `tags: [<skill>, …]` so `--tag <skill>` selects it. Trigger cases also carry `trigger` or `negative-trigger`.
- No grader targets a hook directly. Grade a hook by its effect: a file it writes (`file_exists` / `regex` on the file), or a tool call it blocks (`tool_used` with `max: 0`).

## Rule 1 — every assertion lives in exactly one place

Observable in a sandboxed run → a case under `evals/<skill>/`. Not observable → the `eval.md` spec. Never both. Two copies of one assertion drift; a stale copy then passes a regression it should catch.

A behavior counts as not observable only for a reason on this closed list:

| Reason | Means |
|---|---|
| `cross-plugin` | Needs a skill or agent from another plugin (a run loads only the plugin under test) |
| `interactive` | Sits behind AskUserQuestion or a user reply (runs are non-interactive; `context.history_file` can only test the turn after a reply) |
| `workflow-tool` | Needs the Workflow tool (not in the read-only allowlist, not in the documented grantable list) |
| `host-env` | Needs your home directory, credentials, a device, a real app's data, or ungranted network (home is unreadable under the Bash sandbox; mocks cover MCP tools only) |

Any other reason is not accepted — write the case.

## Rule 2 — both sides always exist

| State | `skills/<skill>/eval.md` | `evals/<skill>/` |
|---|---|---|
| Every behavior observable | Pointer form | Cases |
| Some observable | Mixed form | Cases |
| None observable | Spec form | `NOTE.md` |

**Pointer form** (the whole file):

```markdown
# <skill> Eval

Cases: `evals/<skill>/` — run with `claude plugin eval <plugin-dir> --tag <skill> --no-publish`. This file holds no assertions.
```

**Mixed form**: the title, the same `Cases:` line, then only the sections that stay as spec. **Spec form**: the title, then the sections. In both, every retained section starts with one line `Not observable: <reason>[, <reason>]` using the closed list.

**`NOTE.md`** (the whole file):

```markdown
Not observable: <reason>[, <reason>]
Spec: `skills/<skill>/eval.md`
<one sentence naming the behavior that blocks a case>
```

The CLI ignores a directory that holds only `NOTE.md`. A plugin with zero cases prints `No eval cases found` — skip the run and report that; it is not a failure.

## `eval.md` sections (mixed and spec forms)

```markdown
## Trigger Tests
Not observable: <reason>
- "{prompt that should trigger}"

## Negative Trigger Tests
Not observable: <reason>
- "{prompt that should not trigger}"

## Output Assertions
Not observable: <reason>[, <reason>]
- [ ] {assertion}

## Redundancy Risk
Not observable: <reason>
Baseline comparison: {can the base model do this without the skill?}
Last tested model: {model}
Last tested date: {date}
Verdict: {essential / monitor / likely-redundant}
```

- Machine-parseable: trigger lines match `^- ".*"` under their heading; assertions match `^- \[ \] .*$` under `## Output Assertions`.
- Triggering is almost always observable (`tool_used` on `Skill`), so Trigger sections rarely stay in `eval.md`.
- For a skill with cases, `--ablation with-without` measures what Redundancy Risk used to estimate by hand. Keep Redundancy Risk only where the skill's value is not observable.

## Case recipes

`prompt.md` for a trigger case:

```markdown
---
tags: [<skill>, trigger]
max_turns: 3
allowed_tools: [Read, Glob, Grep, Skill]
---
<the request, phrased the way a user types it>
```

`graders/skill-fired.md` — the skill fired:

```markdown
---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?<skill>"'
---
```

`graders/skill-not-fired.md` — the skill did not fire:

```markdown
---
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?<skill>"'
min: 0
max: 0
arm: both
---
```

`arm: both` is required on a negative check: in a two-arm run every `tool_used` grader on `Skill` is excluded from the score unless it carries `arm: both`, so an unmarked negative check scores nothing.

**Reading a trigger result.** A trigger case observes whether the skill is Claude's first move within `max_turns`. When it fails, Claude went off to do the task itself — searching for the file the prompt names, or writing it directly. With a small `max_turns` that proves "not the first move", not "never fires"; rerun the failing cases with a larger `max_turns` before rewriting the description.

**Slash-typed prompts are not trigger cases.** A prompt starting with `/<skill>` expands the skill directly and produces no `Skill` tool call (verified 2026-09-12: the run's first action was a Read of the skill's own reference file, with `Skill` called 0×). There is no routing to test. To cover a slash-invoked flow, grade its first action instead — e.g. `type: tool_used`, `tool: Read`, `input_match: '<skill>/<route-file>\.md'`.

Output assertions: `regex` (on the final reply or `{ source: file, path: … }`), `file_exists`, `tool_order`, or `llm` (short outputs only, rubric written as concrete PASS / FAIL conditions). Give each case one grader on the result and one on how Claude got there.

**Grader pitfalls** (verified 2026-09-12 while building `dev-workflow/evals/fix-bug/`; details in its `FINDINGS.md`):

- An `llm` grader with `focus: trace` sees only the trace's head and tail; the middle, where Write / Edit calls sit, is elided. Grade what a file became with `focus: { source: file, path: … }`, one file per grader.
- A prompt starting with `/<plugin>:<skill>` makes the without-arm reply `Unknown command` at $0, so Δ is fake. Name the skill in prose instead.
- `allowed_tools` alone does not grant Write / Edit / Bash; the run also needs a matching `--allow-tools`, or every file grader scores 0 in both arms.
- A rubric clause of the form "does not do X" fails good answers; keep negative checks to `regex` / `tool_used`.
- `--keep-temp` sandboxes are sealed mode 000 (`chmod 700 <dir> <dir>/sealed`; final files under `sealed/home/cwd/`) — use them to dry-run a new file grader against an old run for $0.

## Shipping

- `evals/` is part of the plugin and ships with it. `evals/results/` is gitignored (indie-toolkit: `*/evals/results/`; in another repo, add the equivalent line).
- Cases, graders, and fixtures carry no absolute home paths and nothing credential-shaped. Check: `test -d <plugin>/evals` succeeds, then `grep -rnE '/Users/|/home/' <plugin>/evals --exclude-dir=results` exits 1 (no match). Exit 2 is an error, not a pass.

## Running

**Probe first.** `claude plugin eval --help` exits 0 → available. Otherwise report `claude plugin eval unavailable (claude --version → {version}; needs ≥ 2.1.269)`, still write the cases, and do not run them. Never skip the step silently.

**Load check — mandatory after writing or editing cases, costs $0:**

```bash
claude plugin eval <plugin-dir> --tag <skill> --max-cost-usd 0 --trust-plugin --no-publish
```

It loads and validates every selected case and runs none. Pass = no `✗ … prompt.md:` load errors and the line `cost ceiling $0 hit`. Exit code 2 is expected here. When every selected skill is in spec form the CLI prints `No eval cases found` instead — that is also a pass.

**Target is a path, never a bare name.** `claude plugin eval skill-master` resolves to the *installed* copy (`~/.claude/plugins/cache/…`) and reports `No eval cases found` for cases you just wrote in the repo; pass `./skill-master` (or any path with a `/`).

**Depth follows what changed, not how much.** Every run loads the whole plugin, so a one-line description edit is the change most likely to reroute sibling skills.

| What changed | Run |
|---|---|
| Description / trigger wording | `--tag <skill>` plus every sibling's trigger cases (`--tag trigger --tag negative-trigger`) |
| Body / contract | `--tag <skill>` |
| New skill | `--tag <skill>` with the default `--ablation with-without` (Δ is the evidence the skill earns its place), plus siblings' trigger cases |
| Release | Full suite |

**Before any run beyond the load check**, tell the user the case count, `--runs`, and `--ablation` mode, and get a yes: every run is a real model call on their account (cases × runs × arms, plus three judge calls per `llm` / `baseline` grader per run). Runs are local and on demand; they are not wired into CI.

- Pass `--no-publish` unless the user asked for a published report — the default publishes it to claude.ai.
- Non-interactive runs need `--trust-plugin`; pass it only for a plugin the user would run on their own machine.
- A run that hits a usage or rate limit scores 0 and the suite is not marked partial. Check the `NOTES` column (or `cases[].arms.with[].error` in the JSON) before reading a low score as a regression.
- Compare against the previous run by reading both `evals/results/<timestamp>/aggregate-result.json` files: `aggregates.overallScore`, `aggregates.meanDelta`, and per-case `cases[].aggregates.score`.

## Migrating an existing skill

Migrate when the skill is next modified, not in bulk.

1. Trigger prompts in `eval.md` → trigger cases under `evals/<skill>/`.
2. Observable Output Assertions → graders on cases; the rest stay as spec with a `Not observable:` line.
3. Rewrite `eval.md` to pointer or mixed form; add `NOTE.md` if no case was possible.
4. Run the load check.
5. Grep `*/eval.md` and `*/evals/**` for assertions of the behavior you just changed — a stale assertion passes the regression it should catch.

## Trigger prompts for skill-creator

`run_loop` / `run_eval.py` read an eval set of `{"query": "...", "should_trigger": true|false}` items (`run_eval.py` reads `item["query"]`). Build it from the skill's cases: for each case under `evals/<skill>/` with a grader of `type: tool_used` / `tool: Skill`, the `prompt.md` body is `query`; `max: 0` → `should_trigger: false`, otherwise `true`. Fall back to the `eval.md` Trigger sections only for a skill whose triggering is on the spec side.
