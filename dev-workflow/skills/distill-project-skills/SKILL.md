---
name: distill-project-skills
description: "Use when a project has accumulated repeat patterns in untagged main-session turns and you want to identify which patterns are worth promoting as NEW skills. Triggers: 'distill skills', 'mine project patterns', '找重复模式', '看哪些值得做成 skill', 'distill-project-skills', '提炼项目 skill', '挖项目模式'. Scans session jsonl + cost-hint.log, returns candidates with frequency, est wasted spend, suggested cost-posture, and dedup status against existing skills + 30-day declined history; then prompts you per candidate and orchestrates creation via plugin-dev:skill-development with enforced frontmatter. Requires user approval — not autonomous. Not when: project has <7 days of session data. Not when: tuning an existing skill's description from telemetry — use skill-master insights (that route improves WHAT EXISTS; this skill identifies WHAT'S MISSING from main-session patterns). Not when: you already know which skill to build and only need scaffolding + eval — use skill-creator. Not when: you want codebase-pattern-based automation recommendations without telemetry — use claude-automation-recommender. Not when: extracting structure from a discussion file — use distill-discussion. Not when: recording settled decisions to a crystal — use crystallize."
user-invocable: true
argument-hint: "[project-path] (default: cwd)"
allowed-tools: Bash, Read, Write, Edit, Skill, AskUserQuestion
---

# Distill Project Skills

Identifies recurring patterns in untagged main-session work, deduplicates against existing skills + prior decisions, then orchestrates creation of new skills with enforced cost-posture frontmatter.

The whole flow runs in the main session (no fork) because Step 4 requires AskUserQuestion and Step 5 dispatches another skill — both impossible inside a forked context.

## Side effects

- Appends one line per presented candidate to `${PROJECT}/.claude/distill-history.jsonl`. This is how the next run knows what was already built or recently declined.
- AT THE END of a successful run (Step 6 below), archives `${PROJECT}/.claude/cost-hint.log` to `cost-hint-archive-YYYY-MM.log` and empties the primary log. If the run aborts before Step 6, the log is preserved — re-running from scratch is safe.
- The scanner script (Step 1) is called with `--no-archive` so it does not rotate the log unilaterally; archiving is now an explicit final step.

## Process

### Step 1: Scan

```bash
PROJECT="${1:-$(pwd)}"
python3 ${CLAUDE_SKILL_DIR}/scripts/scan.py "$PROJECT" --no-archive --output /tmp/distill-candidates.json
```

The scanner output `/tmp/distill-candidates.json`:

```json
{
  "candidates": [
    {
      "pattern": "grep-recursive",
      "frequency": 59,
      "est_cost_usd": 43.07,
      "suggested_name": "codebase-search",
      "suggested_frontmatter": {"model": "sonnet", "context": "fork"},
      "status": "new"
    }
  ],
  "meta": {
    "existing_skill_count": 994,
    "history_entries": 0,
    "declined_ttl_days": 30
  }
}
```

`status` ∈ {`new`, `name-exists`, `possibly-covered`, `already-built`}.
Candidates with `outcome=declined` in history within 30 days are already filtered out by the scanner.

### Step 2: Present candidates table

Read `/tmp/distill-candidates.json`. Print one row per candidate:

```
| # | Pattern | Freq | Est $ | Suggested Name | Model/Context | Status | Covered By |
|---|---------|-----:|------:|----------------|---------------|--------|------------|
```

Meta line: `Scanned N existing skills, M history entries (declined TTL=30d).`

If `candidates` is empty: stop here with "No new patterns above MIN_FREQUENCY (3) — all declined recently or already built."

### Step 3: Eligibility classification

- **Eligible for creation**: `status == "new"`
- **Informational only**: `status ∈ {name-exists, possibly-covered, already-built}` — shown for context, NOT in the default creation list

### Step 4: User selection

Use AskUserQuestion (multi-select) with this shape:

```
Question: "Which new patterns to promote into skills?"
Options (one per new candidate):
  - "<suggested_name> (freq=X, model=Y/context=Z)"
  - ... (each new candidate as a separate option)
```

If any non-new (informational) rows exist, ALSO ask a follow-up override question:

```
Question: "Any flagged candidates you want to build anyway (override dedup)?"
Options (one per name-exists / possibly-covered candidate):
  - "<suggested_name> (currently flagged: <status> by <covered_by.name>)"
  - "None — accept all dedup flags"
```

Treat user's "yes" on override as promoting that candidate to the creation set. `already-built` candidates are NEVER overrideable — those represent skills distill itself has previously built.

After both questions, compute `accepted_set = (new-selected) ∪ (override-selected)`.

### Step 5: Per-candidate create + verify loop

For EACH `c` in `accepted_set`:

1. **Build prompt** for plugin-dev:skill-development:

```
Create a new skill named "<c.suggested_name>" that does the following work:
<one-line purpose derived from c.pattern; e.g. "wraps recursive grep into a forked sub-agent call">

REQUIRED FRONTMATTER (these are non-negotiable; do not prompt the user to override):
  name: <c.suggested_name>
  description: <appropriate trigger description for this pattern>
  model: <c.suggested_frontmatter.model>
  context: <c.suggested_frontmatter.context>
  user-invocable: true

Place the new skill at: dev-workflow/skills/<c.suggested_name>/
(or the project's appropriate skill directory)
```

2. **Dispatch**: `Skill("plugin-dev:skill-development")` with the prompt above.

3. **Locate the created SKILL.md** — plugin-dev:skill-development returns the file path in its summary, or use `Glob` against the placement directory.

4. **Verify frontmatter**:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/verify_frontmatter.py \
  <created-path> \
  --expect-model <c.suggested_frontmatter.model> \
  --expect-context <c.suggested_frontmatter.context>
```

5. **If verify exits 1** (mismatch): `Edit` the new SKILL.md frontmatter to match expected values, then re-run verify. This is distill's safety net — plugin-dev:skill-development is guidance-only and does not enforce frontmatter, so distill closes the loop here.

6. **Append history entry** (use `Write` or `Bash echo >>`):

   - On success: `{"ts":"<now ISO8601>","pattern":"<c.pattern>","suggested_name":"<c.suggested_name>","outcome":"created","created_path":"<path>","actual_frontmatter":{"model":"...","context":"..."}}`
   - On any failure (dispatch failed, file not created, verify failed AND Edit failed): `{"ts":"<now>","pattern":"<c.pattern>","suggested_name":"<c.suggested_name>","outcome":"error","error":"<short reason>"}`

7. **On error: CONTINUE to next candidate** — do not abort the batch. Each candidate is independent.

### Step 5b: Record declined / deferred outcomes

For EACH candidate presented in Step 2 but NOT in `accepted_set`:

- If `status == "new"` (user saw it, didn't pick it): append `{"ts":"<now>","pattern":"...","suggested_name":"...","outcome":"declined"}` — this hides the pattern from scans for 30 days
- If `status ∈ {name-exists, possibly-covered}` and the user declined override: append `{"ts":"<now>","pattern":"...","suggested_name":"...","outcome":"declined"}` — same effect
- `already-built` candidates: skip (their history is already recorded)

### Step 6: Archive cost-hint.log (final step, post-creation)

After Step 5 completes — even if some candidates errored — rotate the log:

```bash
PROJECT="${1:-$(pwd)}"
LOG="${PROJECT}/.claude/cost-hint.log"
if [ -s "$LOG" ]; then
  MONTH=$(date +%Y-%m)
  cat "$LOG" >> "${PROJECT}/.claude/cost-hint-archive-${MONTH}.log"
  : > "$LOG"
  echo "[archived] $LOG → cost-hint-archive-${MONTH}.log"
fi
```

If the user invoked with `--no-archive` as the second arg (rare; mainly for debugging), skip this step.

### Step 7: Summary back to user

Report:
- **Created**: N skills, with paths
- **Declined**: M patterns (won't reappear for 30 days)
- **Errored**: K patterns (with short reason for each)
- **Informational (not built)**: L patterns flagged by dedup, user did not override

## Completion criteria

- `/tmp/distill-candidates.json` exists with `candidates[].status` populated
- `distill-history.jsonl` has one entry per candidate presented in Step 2 (created/declined/error)
- `cost-hint.log` archived if non-empty (or explicitly skipped via `--no-archive`)
- User received Step 7 summary
- For each `created` entry: the file at `created_path` exists AND its frontmatter matches the `actual_frontmatter` field
