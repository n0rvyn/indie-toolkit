#!/usr/bin/env bash
# readback: stop — quiet tally; warn only when threshold met
# Schema v2: two-phase identity (Pending TTL + Confirmed sid-stamped). See
# readback/references/state-schema.md for the lifecycle contract.
# Per DP-002=B: count Write/Edit/MultiEdit calls in the LAST assistant turn only,
# using jq to parse jsonl turn boundaries (not full-file grep).
set -e
trap 'echo "{}"; exit 0' ERR

INPUT=$(cat)

TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty')
[ -r "$TRANSCRIPT_PATH" ] || { echo "{}"; exit 0; }

# Transcript schema (jsonl line shape: {type, message:{content:[]}}) verified
# against Claude Code v2.x. Update if schema changes.
# Parse jsonl: keep only objects of {"type":"assistant"}, take the LAST one,
# walk message.content[] for tool_use entries, count Write/Edit/MultiEdit.
WRITE_COUNT=$(jq -s '
  map(select(.type == "assistant")) | last
  | .message.content // []
  | map(select(.type == "tool_use" and (.name | test("^(Write|Edit|MultiEdit|NotebookEdit)$"))))
  | length
' "$TRANSCRIPT_PATH" 2>/dev/null || echo "0")

# Threshold check (per Task Contract: ≥3 Write/Edit in this turn)
[ "${WRITE_COUNT:-0}" -ge 3 ] || { echo "{}"; exit 0; }

# Check readback state
STATE_FILE=".claude/readback-state.json"
if [ -r "$STATE_FILE" ]; then
  # Read fields. session_id arrives via stdin JSON (Claude Code hook contract).
  STORED_SID=$(jq -r '.session_id // empty' "$STATE_FILE" 2>/dev/null || echo "")
  # Normalize v1 schema residue: treat "unknown" identically to null
  [ "$STORED_SID" = "unknown" ] && STORED_SID=""
  CURRENT_SID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null || echo "")
  CREATED_AT=$(jq -r '.created_at // empty' "$STATE_FILE" 2>/dev/null || echo "")
  CONFIRMED_AT=$(jq -r '.confirmed_at // empty' "$STATE_FILE" 2>/dev/null || echo "")
  SKILL=$(jq -r '.skill // empty' "$STATE_FILE" 2>/dev/null || echo "")
  CONFIRMED=$(jq -r '.user_confirmed // false' "$STATE_FILE" 2>/dev/null || echo "false")

  # Phase 1: pending state past 30-min TTL → treat as no-readback (emit warning)
  if [ "$CONFIRMED" != "true" ] && [ -n "$CREATED_AT" ]; then
    # Note: BSD date -j needs -u to parse ISO 8601 Z-suffix as UTC, not local.
    if NOW_TS=$(date -u +%s 2>/dev/null) \
       && CREATED_TS=$( (date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$CREATED_AT" +%s 2>/dev/null) \
                       || (date -d "$CREATED_AT" +%s 2>/dev/null) ); then
      AGE=$((NOW_TS - CREATED_TS))
      if [ "$AGE" -gt 1800 ]; then
        SKILL=""; CONFIRMED="false"
      fi
    fi
  fi
  # Phase 2: confirmed + sid mismatch → treat as no-readback (emit warning)
  if [ "$CONFIRMED" = "true" ] && [ -n "$STORED_SID" ] && [ -n "$CURRENT_SID" ] \
     && [ "$STORED_SID" != "$CURRENT_SID" ]; then
    SKILL=""; CONFIRMED="false"
  fi
  # Phase 3: confirmed + empty stored sid + stale confirmed_at (>30 min) →
  # state leaked from a prior session where pre-tool-use.sh never stamped
  # (e.g., /readback without subsequent Write/Edit, or skill != fix-bug).
  # Treat as no-readback so the warning fires. Mirrors user-prompt-submit.sh
  # TTL fix for state-leak prevention (audit fix 2026-05-25).
  if [ "$CONFIRMED" = "true" ] && [ -z "$STORED_SID" ] && [ -n "$CONFIRMED_AT" ]; then
    if NOW_TS=$(date -u +%s 2>/dev/null) \
       && CONF_TS=$( (date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$CONFIRMED_AT" +%s 2>/dev/null) \
                    || (date -d "$CONFIRMED_AT" +%s 2>/dev/null) ); then
      AGE=$((NOW_TS - CONF_TS))
      if [ "$AGE" -ge 1800 ]; then
        SKILL=""; CONFIRMED="false"
      fi
    fi
  fi

  # Skip warning when skill orchestration is active (run-phase et al ran the writes)
  case "$SKILL" in
    run-phase|execute-plan|verify-plan) echo "{}"; exit 0 ;;
  esac
  [ "$CONFIRMED" = "true" ] && { echo "{}"; exit 0; }
fi

# Emit warning for next turn
jq -n --arg n "$WRITE_COUNT" '{
  hookSpecificOutput: {
    hookEventName: "Stop",
    additionalContext: "[readback-warning] Previous turn wrote/edited \($n) files without a confirmed readback. Consider dispatching readback:intent-echoer before further multi-file edits, or use /readback to confirm intent retroactively."
  }
}'
