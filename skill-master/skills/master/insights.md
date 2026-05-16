---
allowed-tools: Read, Bash(python3:*), Bash(gh pr create:*), Bash(gh --version:*), Bash(git:*)
---

# insights Route

Analyzes real usage data from the skill-master SQLite database to propose targeted, evidence-based improvements to plugin skill descriptions.

Invocation forms (both supported via master routing):

- Slash: `/master insights [--focus <skill_name>] [--window <days>] [--dry-run]`
- Natural language: routes here whenever the master entry-point matches keywords like "insights" / "usage data" / "auto-tune" / "propose improvements". In NL form, ask the user once for `--focus` / `--window` / `--dry-run` defaults if not stated.

## Args

| Arg | Description | Default |
|-----|-------------|---------|
| `--focus <skill_name>` | Limit analysis to a single skill | all skills |
| `--window <days>` | Lookback window in days | 14 |
| `--dry-run` | Run preflight + Reader + Proposer + judge but do NOT open a PR | false |

## Process

### Step 1: Preflight

Run all preflight checks, passing the repo root explicitly:

```python
from pathlib import Path
from scripts.preflight import run_all
run_all(repo_root=Path.cwd())
```

`preflight.run_all()` validates:
- session-reflect SQLite database exists and is readable
- DB schema includes Phase 5 columns (`invocation_trigger`, etc.) — fail-fast with actionable message otherwise
- `marketplace.json` is parseable and lists indie-toolkit plugins
- `gh` CLI is on PATH (`gh --version` returns 0)

If any check fails: report the failure reason to the user and exit. Do NOT proceed to Step 2.

**Note**: preflight does NOT check `gh auth status`, git working-tree cleanness, or the `skill-master-insights.lock` state. Those concerns are handled later: lock is acquired inside `pr_composer.run`; `gh` auth is exercised lazily at `gh pr create` time; git cleanliness is the user's responsibility (the route runs on whatever HEAD is checked out).

### Step 2: Reader — Fetch Usage Data

Call the Q1–Q5 query functions in `insights_reader.py` to assemble findings:

```python
from scripts.insights_reader import (
    freq_and_error_rate,
    description_misfires,
    agent_efficiency,
    agent_skill_choreography,
    post_commit_anomalies,
)

window_days = <window>     # from --window arg, default 14
plugin_filter = <focus>    # from --focus arg, None for all skills

def _rows(q): return q.get("rows", []) if isinstance(q, dict) else q
def _lag(q):  return q.get("lag_warning") if isinstance(q, dict) else None

q1 = freq_and_error_rate(window_days, plugin_filter=plugin_filter)
q2 = description_misfires(window_days)
q3 = agent_efficiency(window_days)
q4 = agent_skill_choreography(window_days)

# Q5 takes (plugin, component) — iterate over Q1's distinct rows
q5_rows = []
for r in _rows(q1):
    plugin = r.get("plugin")
    component = r.get("component")
    if plugin and component:
        anomalies = post_commit_anomalies(plugin, component, window_days=window_days)
        q5_rows.extend(_rows(anomalies))

# Lag warning is identical across all Q outputs (computed from same DB / JSONL diff).
lag_warning = _lag(q1)

findings = {
    "window_days": window_days,
    "freq_and_error_rate": _rows(q1),
    "description_misfires": _rows(q2),
    "agent_efficiency": _rows(q3),
    "agent_skill_choreography": _rows(q4),
    "post_commit_anomalies": q5_rows,
}
```

If all five rows lists are empty: report `"No usage data found in the past {window_days} days. Exiting."` and exit 0.

### Step 3: Dispatch Proposer Agent

Resolve target SKILL.md paths from the findings. For each `(plugin, component)` mentioned in any finding, compute `repo_root / plugin / "skills" / component / "SKILL.md"` (fallback to `agents/{component}.md` if SKILL.md path doesn't exist — e.g. agent components). Read the file's current full text.

Build the **single JSON object** matching Proposer Input Schema and dispatch via the Agent tool:

```json
{
  "window_days": <window>,
  "findings": [...],
  "target_files": [
    {"path": "dev-workflow/skills/verify-plan/SKILL.md", "current_description": "..."},
    ...
  ]
}
```

Dispatch via `Agent(subagent_type="skill-master:proposer", prompt=<json_payload_as_string>)`. The Proposer's system prompt already contains Forbidden / Allowed rules — do NOT append a duplicate reminder (that would risk prompt contamination).

**Timeout expectation**: 60 seconds. Proposer should return:

```json
{"candidates": [...]}
```

**Failure handling**:
- If agent dispatch raises an exception: log `"Proposer agent dispatch failed: {error}"` and exit 1.
- If agent output is not parseable as JSON (e.g., wrapped in markdown despite "JSON only" instruction): log raw output to stderr, treat as `{"candidates": []}`, proceed to Step 4 (which will exit 0 with "No candidates passed validation").
- If `candidates` is empty: continue to Step 4 anyway — Step 4 handles the empty case cleanly.

### Step 4: Validate Candidates

Run each candidate through the mechanical validator:

```python
from scripts.validate_proposal import validate
approved = []
for candidate in proposer_output["candidates"]:
    allow, reason = validate(candidate, repo_root=Path.cwd())
    if allow:
        approved.append(candidate)
    else:
        print(f"Candidate rejected by validator ({candidate.get('file_path', '?')}): {reason}")
```

If `approved` is empty: report `"No candidates passed validation. Exiting."` and exit 0.

### Step 5: Dispatch Judge Agent

Dispatch `skill-master:judge` (DP-V1=D semantic accumulation defense) with the validator-approved candidates:

```json
{
  "candidates": [
    {"candidate_index": 0, "file_path": "...", "change_type": "...", "old_string": "...", "new_string": "...", "evidence_summary": "..."},
    ...
  ],
  "context": {
    "window_days": <window>,
    "lag_warning": <lag_warning or null>
  }
}
```

Dispatch via `Agent(subagent_type="skill-master:judge", prompt=<json_payload_as_string>)`.

**Timeout expectation**: 60 seconds. Judge returns:

```json
{"approvals": [int], "rejections": [{"candidate_index": int, "reason": str}]}
```

**Failure handling**:
- If judge dispatch fails (exception or unparseable output): log warning, **default to deny-all** (per Failure modes table). Exit 0 with `"Judge dispatch failed; no candidates applied (conservative default)."`
- For each rejection: log `"Judge rejected candidate {index} ({file_path}): {reason}"`.
- Filter `approved` to keep only those whose original index is in `judge_output["approvals"]`.

If all candidates were judge-rejected: report `"All candidates rejected by judge. Exiting."` and exit 0.

### Step 6: AskUserQuestion — Confirm Changes

Present the surviving candidates to the user. For each candidate, derive the surface fields needed for display from `file_path`:

```python
def parse_path(file_path: str) -> tuple[str, str]:
    """e.g. 'dev-workflow/skills/verify-plan/SKILL.md' → ('dev-workflow', 'verify-plan')."""
    parts = file_path.split("/")
    return parts[0], parts[2]
```

Then call AskUserQuestion with a single question listing all candidates in the `question` body:

```
Found {N} proposed change(s) to apply:

[1] {plugin} / {component} ({change_type}) — Confidence: {confidence} — Sample: {sample_size} sessions
    Evidence: {evidence_summary}
[2] ...

Apply all, cancel, or review one-by-one?
```

Options: `"Apply all"` / `"Cancel"` / `"Review each"`.

- If user cancels: exit 0.
- If user selects "Review each": loop per-candidate with diff display + per-candidate Yes/No AskUserQuestion. Filter `confirmed` to only Yes selections.
- If user selects "Apply all": `confirmed = approved`.

### Step 7: PR Composer

Run the PR composer with user-confirmed candidates:

```python
from scripts.pr_composer import run
run(
    candidates=confirmed,
    findings=findings,
    lag_warning=lag_warning,
    dry_run=<dry_run_flag>,
)
```

The composer handles (per Threat Model contract):
- Branch creation (`auto-insights/YYYY-MM-DD-{8-char-hash}`)
- `apply_candidates` (DP-V2=A: temp-dir + batch rename, path-mangled filename)
- Commit with `chore(insights):` prefix (raises `ValueError` on `feat`/`fix`)
- Push and `gh pr create --draft`
- SIGINT three-state rollback (local-only / pushed-no-PR with remote cleanup / PR-created no rollback)
- `fcntl.flock` on `~/.claude/skill-master-insights.lock`

If `--dry-run`: composer exits after printing what it would do, without creating a branch or PR.

### Step 8: Record State

After the PR is created (or dry-run completes), record proposal hashes to prevent re-proposal within the cooldown window:

```python
from scripts.state import record_proposal, compute_hash

def parse_path(file_path: str) -> tuple[str, str]:
    parts = file_path.split("/")
    return parts[0], parts[2]

for candidate in confirmed:
    plugin, component = parse_path(candidate["file_path"])
    h = compute_hash(
        plugin=plugin,
        component=component,
        change_type=candidate["change_type"],
        evidence_keys=candidate.get("evidence_keys", []),
    )
    record_proposal(h)
```

Output the PR URL to the user.

## Failure Modes

| Failure | Behavior |
|---------|----------|
| Preflight fails | Exit with failure reason; no further action |
| No usage data | Exit 0; "No usage data" message |
| Proposer agent dispatch fails (exception) | Exit 1; report error |
| Proposer output is non-JSON | Treat as 0 candidates; fall through to Step 4 clean exit |
| No candidates pass validator | Exit 0; "No candidates passed validation" |
| Judge agent dispatch fails | Exit 0; deny-all (conservative); no PR opened |
| All candidates judge-rejected | Exit 0; report rejections |
| User cancels in Step 6 | Exit 0 |
| pr_composer push fails | Rollback local branch; report to user |
| pr_composer push succeeds, PR create fails | Rollback local + remote branch; report to user |
| PR created | No rollback; user decides to close |

## Forbidden Changes

The following changes are FORBIDDEN. The `validate_proposal.py` validator enforces these at runtime. Any candidate that violates these rules will be rejected before reaching the judge or the user.

1. **Frontmatter fields**: Do NOT change `allowed-tools`, `model`, `name`, `version`, `tools`, or any other frontmatter key except `description`.
2. **`## Process` section**: Do NOT modify any `## Process`, `## Steps`, or `## Step N:` sections in any SKILL.md.
3. **Deleting existing content**: Do NOT remove any existing non-empty prose, steps, or sections.
4. **Quote blocks in PR body**: Do NOT include `>` quote blocks in the PR body (prevents user prompt leak). Exception: `<!--lag-meta-->` sentinel lines from `render_pr_body` are allowed.
5. **Paths outside repo**: Do NOT target files with `..` or absolute paths that exit the repository root.
6. **Edit tool on skill files**: This route does NOT use `Edit(*/skills/*)` or `Write(*/skills/*)`. Skill file edits are applied by `pr_composer.py` via direct Python file I/O, not the Claude Edit tool.

## Allowed Changes

The following are the ONLY permitted change types (the `change_type` enum):

1. **`description_update`**: Replace the `description` field value in the frontmatter with an improved trigger description. The new description must be derived from real usage evidence (correction patterns, invocation patterns).
2. **`append_examples_section`**: Add a new `## Examples` section at the end of a SKILL.md that has no existing `## Examples` section. Each example must be grounded in real usage patterns.
