---
name: audit-tokens
description: "Use when the user says 'audit tokens', 'token audit', 'analyze token consumption', '审计 token', '分析 token 消耗', '查 token 开销', 'cost audit', 'token consumption analysis', or wants a multi-dimensional analysis of Claude Code session token consumption with HTML report. Accepts integer days or natural-language window ('today', 'last week', 'last month'). Reads ~/.claude/projects/ session jsonl files, aggregates spend by skill/model/project/date/tool, identifies optimization opportunities using the cost-posture heuristic, and writes a self-contained HTML report. Not when: user wants to monitor live token usage during a session — that's /context. Not when: user wants quota check for a specific model provider — that's minimax-coding-plan. Not when: user wants the official Claude Code session HTML report — use claude-plugins-official:session-report (overlapping source: ~/.claude/projects transcripts)."
user-invocable: true
model: sonnet
context: fork
argument-hint: "[days|window]"
allowed-tools: Bash(bash:*), Bash(python3:*), Bash(open:*), Bash(date:*), Bash(mkdir:*), Read, Write
---

# Audit Token Consumption

Multi-dimensional analysis of Claude Code session token consumption over a date window. Reads raw session jsonl, aggregates by skill / model / project / date / tool / sidechain, applies the cost-posture heuristic to flag optimization gaps, and writes a self-contained HTML report.

## Process

### Step 1: Parse arguments → assign `DAYS`

- `$1` (optional): days to look back. Default `3`. Acceptable: integer 1–365 OR a natural-language window: "today" → 1, "last week" → 7, "last month" → 30, "last year" → 365.
- Resolve to an integer and **store it in a shell variable named `DAYS`** that Steps 2 and 3 will consume. Do not pass the literal string `<days>` to scripts.

Echo the chosen window to user: "Auditing last $DAYS days of session data."

### Step 2: Run analyzer

Execute the analysis pipeline. The script writes raw TSV to a temp file:

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/analyze.sh "$DAYS" /tmp/audit-tokens-raw.tsv
```

The script (invoked via `bash` so a single `Bash(bash:*)` permission rule covers it):
1. Preflight: checks `jq` is on PATH; exits with a clear error message if not.
2. Finds all `*.jsonl` under `~/.claude/projects/` modified within `$DAYS` × 24h
3. One-shot jq extraction of `assistant` messages with usage (handles missing `cache_creation` via guarded path)
4. Dedupes by (sessionId, requestId) compound key so that rows with missing requestId from different sessions are preserved
5. Writes TSV with 14 columns: sessionId, requestId, attributionSkill, attributionPlugin, model, input_tokens, cache_creation, cache_read, output_tokens, ephemeral_1h, ephemeral_5m, isSidechain, cwd, timestamp

If the TSV has <10 rows or exit code is non-zero: stop and report the script's stderr to the user (typically "jq not installed" or "no jsonl files in window").

### Step 3: Generate HTML report

```bash
TS=$(date +%Y%m%d-%H%M%S)
OUT=~/Desktop/token-audit-${TS}.html
python3 ${CLAUDE_SKILL_DIR}/scripts/generate_report.py /tmp/audit-tokens-raw.tsv "$OUT" "$DAYS"
```

The Python script:
- Reads the TSV
- Computes all aggregates (overall totals, per-skill, per-model, per-project, daily, tool calls, sidechain split, cache TTL split, cost composition)
- Scans installed plugin SKILL.md files for cost-posture gaps (skills without `model:` that look mechanical/retrieval/tool-wrapper)
- Emits a single self-contained HTML file (inline CSS, no JS, no external deps)
- Prints the output path to stdout

Open the report:

```bash
open "$OUT"
```

### Step 3.5: Run cost-driver diagnosis (default-on; fail-open)

Execute the bundled diagnose.py script directly:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/diagnose.py \
  /tmp/audit-tokens-raw.tsv \
  /tmp/diagnose-fragment.html 2>/tmp/diagnose-stderr.log || true
```

If `diagnose-fragment.html` exists and is non-empty: read it and inject the contents at the `<!-- DIAGNOSIS -->` placeholder in the HTML output (placeholder lives in `generate_report.py` just before the `<footer>` tag).

If diagnose.py failed or fragment is missing/empty: substitute the placeholder with `<section><h2>Diagnosis & Suggestions</h2><p>Diagnosis unavailable (see /tmp/diagnose-stderr.log).</p></section>` so the report still completes (per "enhance not break" principle).

Note: this is a direct script invocation, not a Skill-tool call. The script is bundled under `scripts/diagnose.py` and owned by audit-tokens.

**Internal dependency**: this step invokes `${CLAUDE_SKILL_DIR}/scripts/diagnose.py` (same variable as Steps 2/3, which run `analyze.sh` and `generate_report.py` from the same `scripts/` dir). The script and audit-tokens are bundled together — relocating diagnose.py requires updating this path.

### Step 4: Summarize in chat

Read the generated HTML file's `<!-- SUMMARY -->` block (the Python script embeds a short machine-readable summary at the top of the HTML as an HTML comment). Present to user:

- Total spend + window
- Top cost driver (highest single line item)
- Top 3 recommendations (taken from the report's recommendations section)
- HTML path

Do NOT paste the full HTML or large tables into chat. The HTML is the deliverable; chat gets the executive summary only.

## Completion criteria

- Raw TSV written to `/tmp/audit-tokens-raw.tsv`
- Diagnosis fragment injected into HTML report at `<!-- DIAGNOSIS -->` (or fallback "Diagnosis unavailable" section if diagnose.py failed — fail-open per Principle 1)
- HTML written to `~/Desktop/token-audit-<timestamp>.html`
- HTML opened in default browser
- 3-bullet summary delivered in chat (total / top driver / top recommendations)
- **Cadence marker written**: `mkdir -p ~/.claude && date -u +%Y-%m-%dT%H:%M:%SZ > ~/.claude/last-audit-tokens-run` — the `suggest-skills.sh` UserPromptSubmit hook reads this file's mtime to compute "days since last audit" and suppress its 14-day cadence nudge. Without this write, the bootstrap nudge fires perpetually.

## Notes

- **Pricing assumption**: uses public Anthropic list pricing as of 2026-06 for Opus 4.8 ($5/$25 per 1M in/out) / Sonnet 4.6 / Haiku 4.5. If the user is on a flat-rate plan, the dollar numbers are notional (treat as relative ranking, not actual billing).
- **Cost-posture heuristic**: the recommendations engine cites `skill-master/skills/plugin-master/cost-posture.md` — see that file for the classification rules. If `cost-posture.md` is not installed locally, the report falls back to a built-in subset of the heuristic.
- **Date semantics**: "last N days" means `find -mtime -N`, i.e. files modified within N × 24h of now. Not calendar days. Supports up to 365 days.
- **Cache TTL caveat**: 1h vs 5m split is reported but not actionable — Claude Code's harness decides automatically, no user-side knob.
- **Plugin cache lag**: the recommendations engine reads SKILL.md frontmatter from `~/.claude/plugins/marketplaces/<marketplace>/<plugin>/skills/<name>/SKILL.md` and the versioned `~/.claude/plugins/cache/.../` copies. These reflect the **installed** plugin version, not edits in your local repo. After editing a SKILL.md in the source repo, you must commit → wait for auto-version bump → run `/plugin update` for Claude Code to pull the new version. Until then, a freshly-edited skill will still appear in this report's recommendations as if it lacked the `model:` field.

## Principles

These principles govern HOW cost-engineering work proceeds in this project. They apply both to this skill's evolution and to any cost-related enhancements (hooks, sibling skills, CLAUDE.md rules):

1. **Enhance, not break.** Cost-saving mechanisms NUDGE, not BLOCK. Hooks emit hints to stderr; they do not exit non-zero. Rules are self-applied by the main model; they do not prevent action. The user's flow is sacred — friction added in the name of cost is friction we pay later in user trust.

2. **Recover unwarranted cost only.** Target spend that shouldn't have happened — Opus running on mechanical探查, cache bloat from re-Reading the same file, work that bypassed an existing cheaper skill. Do NOT blanket-downgrade work that needs the quality (orchestration, judgment, synthesis). The goal is not the lowest number on the invoice; the goal is keeping the work that earned its cost and trimming the work that didn't.

Cross-reference: project CLAUDE.md `## Skill Cost Posture` links here.
