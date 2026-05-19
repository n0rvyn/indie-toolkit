---
name: audit-tokens
description: "Use when the user says 'audit tokens', 'token audit', 'analyze token consumption', '审计 token', '分析 token 消耗', '查 token 开销', 'cost audit', 'token consumption analysis', or wants a multi-dimensional analysis of Claude Code session token consumption with HTML report. Accepts integer days or natural-language window ('today', 'last week', 'last month'). Reads ~/.claude/projects/ session jsonl files, aggregates spend by skill/model/project/date/tool, identifies optimization opportunities using the cost-posture heuristic, and writes a self-contained HTML report. Not when: user wants to monitor live token usage during a session — that's /context. Not when: user wants quota check for a specific model provider — that's minimax-coding-plan. Not when: user wants the official Claude Code session HTML report — use claude-plugins-official:session-report (overlapping source: ~/.claude/projects transcripts)."
user-invocable: true
model: sonnet
context: fork
argument-hint: "[days|window]"
allowed-tools: Bash(bash:*), Bash(python3:*), Bash(open:*), Bash(date:*), Read, Write
---

# Audit Token Consumption

Multi-dimensional analysis of Claude Code session token consumption over a date window. Reads raw session jsonl, aggregates by skill / model / project / date / tool / sidechain, applies the cost-posture heuristic to flag optimization gaps, and writes a self-contained HTML report.

## Process

### Step 1: Parse arguments → assign `DAYS`

- `$1` (optional): days to look back. Default `3`. Acceptable: integer 1–30 OR a natural-language window: "today" → 1, "last week" → 7, "last month" → 30.
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

### Step 4: Summarize in chat

Read the generated HTML file's `<!-- SUMMARY -->` block (the Python script embeds a short machine-readable summary at the top of the HTML as an HTML comment). Present to user:

- Total spend + window
- Top cost driver (highest single line item)
- Top 3 recommendations (taken from the report's recommendations section)
- HTML path

Do NOT paste the full HTML or large tables into chat. The HTML is the deliverable; chat gets the executive summary only.

## Completion criteria

- Raw TSV written to `/tmp/audit-tokens-raw.tsv`
- HTML written to `~/Desktop/token-audit-<timestamp>.html`
- HTML opened in default browser
- 3-bullet summary delivered in chat (total / top driver / top recommendations)

## Notes

- **Pricing assumption**: uses public Anthropic list pricing as of 2026-05 for Opus 4.7 / Sonnet 4.6 / Haiku 4.5. If the user is on a flat-rate plan, the dollar numbers are notional (treat as relative ranking, not actual billing).
- **Cost-posture heuristic**: the recommendations engine cites `skill-master/skills/plugin-master/cost-posture.md` — see that file for the classification rules. If `cost-posture.md` is not installed locally, the report falls back to a built-in subset of the heuristic.
- **Date semantics**: "last N days" means `find -mtime -N`, i.e. files modified within N × 24h of now. Not calendar days.
- **Cache TTL caveat**: 1h vs 5m split is reported but not actionable — Claude Code's harness decides automatically, no user-side knob.
- **Plugin cache lag**: the recommendations engine reads SKILL.md frontmatter from `~/.claude/plugins/marketplaces/<marketplace>/<plugin>/skills/<name>/SKILL.md` and the versioned `~/.claude/plugins/cache/.../` copies. These reflect the **installed** plugin version, not edits in your local repo. After editing a SKILL.md in the source repo, you must commit → wait for auto-version bump → run `/plugin update` for Claude Code to pull the new version. Until then, a freshly-edited skill will still appear in this report's recommendations as if it lacked the `model:` field.
