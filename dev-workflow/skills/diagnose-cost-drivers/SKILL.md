---
name: diagnose-cost-drivers
description: "Use when the user wants to root-cause attribute their top expensive Claude Code sessions (sub-agent miss / cache bloat / Read pollution / skill gap), OR says 'diagnose cost', 'why is this expensive', '为什么这么贵', 'cost root cause', '诊断成本', '分析为什么贵', '找出贵的原因'. Reads audit-tokens TSV plus the corresponding session jsonl files (for sub-agent-miss and Read-pollution attribution which TSV alone cannot reveal). Outputs HTML fragment. The same diagnostic script is also invoked automatically by /audit-tokens — this skill is for standalone ad-hoc analysis. Not when: TSV doesn't exist — run /audit-tokens first. Not when: user wants the official Claude Code session HTML report — use claude-plugins-official:session-report (that one renders an explorable transcript browser; this one attributes aggregated rows to root causes)."
user-invocable: true
model: sonnet
context: fork
argument-hint: "[tsv-path] (default: /tmp/audit-tokens-raw.tsv)"
allowed-tools: Bash(python3:*), Read, Write
---

# Diagnose Cost Drivers

Drills into audit-tokens output to attribute top-N expensive sessions to root causes (sub-agent miss / cache bloat / Read pollution / skill gap). Reads BOTH the aggregated TSV AND the source jsonl files — sub-agent miss and Read pollution are computable only from jsonl tool-call sequences, not from the aggregated TSV.

## Process

### Step 1: Locate input

```bash
TSV="${1:-/tmp/audit-tokens-raw.tsv}"
if [ ! -f "$TSV" ]; then
  echo "❌ TSV not found at $TSV. Run /audit-tokens first." >&2
  exit 1
fi
```

### Step 2: Run diagnostic

The script reads the TSV for per-session aggregates and, for each top session, locates the corresponding jsonl (via the `cwd` and `sessionId` columns) to compute sub-agent miss and Read pollution events.

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/diagnose.py "$TSV" /tmp/diagnose-fragment.html
```

### Step 3: Output

- If invoked from `audit-tokens` Step 3.5: read fragment from `/tmp/diagnose-fragment.html`, return it as the result for audit-tokens to inject.
- If invoked standalone: cat the fragment to user, optionally write to a standalone HTML file via Write.

## Completion criteria

- HTML fragment produced (or `❌ TSV not found` exit if input missing)
- If integrated: audit-tokens injects into its report at `<!-- DIAGNOSIS -->` placeholder
- If standalone: user sees the attributions

## Cross-skill dependency

audit-tokens Step 3.5 calls `${CLAUDE_PLUGIN_ROOT}/skills/diagnose-cost-drivers/scripts/diagnose.py` directly (not via Skill tool — audit-tokens runs in `context: fork` and has no Skill in `allowed-tools`). Renaming this skill or moving the script requires updating `dev-workflow/skills/audit-tokens/SKILL.md` Step 3.5.
