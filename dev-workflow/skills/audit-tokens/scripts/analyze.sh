#!/usr/bin/env bash
# audit-tokens: extract per-turn usage data from Claude Code session jsonl files.
# Output: TSV with 14 columns, deduped by requestId.
#
# Usage: analyze.sh <days> [out_path]
#   days     — look-back window (1..30). Default 3.
#   out_path — TSV output path. Default /tmp/audit-tokens-raw.tsv

set -euo pipefail

DAYS="${1:-3}"
OUT="${2:-/tmp/audit-tokens-raw.tsv}"

# Validate days
if ! [[ "$DAYS" =~ ^[0-9]+$ ]] || [ "$DAYS" -lt 1 ] || [ "$DAYS" -gt 30 ]; then
  echo "error: days must be an integer 1..30, got: $DAYS" >&2
  exit 2
fi

PROJECTS_DIR="${HOME}/.claude/projects"

if [ ! -d "$PROJECTS_DIR" ]; then
  echo "error: $PROJECTS_DIR does not exist" >&2
  exit 1
fi

# Preflight: jq is required and not shipped by default on macOS
if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq not installed. Install via 'brew install jq' (macOS) or your distro's package manager (Linux)." >&2
  exit 4
fi

# One-shot: find all jsonl modified within window, cat them, jq-extract, dedup by (sessionId, requestId).
# Compound dedup key preserves distinct rows even when requestId is missing or "_" (synthetic placeholders
# from different sessions would otherwise collapse to a single row with a single-column dedup).
find "$PROJECTS_DIR" -name "*.jsonl" -mtime "-${DAYS}" -type f -print0 2>/dev/null \
  | xargs -0 cat 2>/dev/null \
  | jq -r '
      select(.type=="assistant" and (.message.usage != null)) |
      [
        .sessionId // "_",
        .requestId // "_",
        (.attributionSkill // "_none_"),
        (.attributionPlugin // "_none_"),
        (.message.model // "_"),
        (.message.usage.input_tokens // 0),
        (.message.usage.cache_creation_input_tokens // 0),
        (.message.usage.cache_read_input_tokens // 0),
        (.message.usage.output_tokens // 0),
        ((.message.usage.cache_creation | if . then .ephemeral_1h_input_tokens else 0 end) // 0),
        ((.message.usage.cache_creation | if . then .ephemeral_5m_input_tokens else 0 end) // 0),
        ((.isSidechain // false) | tostring),
        (.cwd // "_"),
        (.timestamp // "_")
      ] | @tsv
    ' 2>/dev/null \
  | sort -u -t$'\t' -k1,2 > "$OUT"

ROWS=$(wc -l < "$OUT" | tr -d ' ')
echo "wrote $ROWS rows to $OUT"
