#!/usr/bin/env bash
# readback: pre-tool-use — hard-block Write/Edit when fix-bug readback not confirmed
# Schema v2: two-phase identity (Pending TTL + Confirmed sid-stamped). See
# readback/references/state-schema.md for the lifecycle contract.
set -e
trap 'echo "{}"; exit 0' ERR

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')

# Only intercept Write/Edit/MultiEdit/NotebookEdit
case "$TOOL" in
  Write|Edit|MultiEdit|NotebookEdit) ;;
  *) echo "{}"; exit 0 ;;
esac

# Project root is cwd (Claude Code launches hooks in project root)
STATE_FILE=".claude/readback-state.json"

# Fail-open if state file missing or unreadable
[ -r "$STATE_FILE" ] || { echo "{}"; exit 0; }

# Read fields. session_id arrives via stdin JSON (Claude Code hook contract), NOT env var.
STORED_SID=$(jq -r '.session_id // empty' "$STATE_FILE" 2>/dev/null || echo "")
# Normalize v1 schema residue: treat "unknown" identically to null
[ "$STORED_SID" = "unknown" ] && STORED_SID=""
CURRENT_SID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null || echo "")

SKILL=$(jq -r '.skill // empty' "$STATE_FILE" 2>/dev/null || echo "")
CONFIRMED=$(jq -r '.user_confirmed // false' "$STATE_FILE" 2>/dev/null || echo "false")
CREATED_AT=$(jq -r '.created_at // empty' "$STATE_FILE" 2>/dev/null || echo "")

# Only enforce for fix-bug
[ "$SKILL" = "fix-bug" ] || { echo "{}"; exit 0; }

# Phase 1: pending state — apply 30-min TTL from created_at
if [ "$CONFIRMED" != "true" ] && [ -n "$CREATED_AT" ]; then
  # macOS BSD date vs GNU date fallback chain
  # Note: BSD date -j needs -u to parse ISO 8601 Z-suffix as UTC, not local.
  # GNU date -d parses Z-suffix as UTC by default; -u on GNU date controls output, not input,
  # so the GNU fallback is unaffected by the -u flag.
  if NOW_TS=$(date -u +%s 2>/dev/null) \
     && CREATED_TS=$( (date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$CREATED_AT" +%s 2>/dev/null) \
                     || (date -d "$CREATED_AT" +%s 2>/dev/null) ); then
    AGE=$((NOW_TS - CREATED_TS))
    if [ "$AGE" -gt 1800 ]; then
      # Pending state expired (> 30 min) → stale → allow
      echo "{}"; exit 0
    fi
  fi
fi

# Phase 2: confirmed state — sid match drives enforcement
if [ "$CONFIRMED" = "true" ]; then
  if [ -z "$STORED_SID" ] && [ -n "$CURRENT_SID" ]; then
    # First read of confirmed state: stamp stdin sid into the file (atomic rewrite)
    TMP_STATE=$(mktemp "${STATE_FILE}.XXXXXX")
    if jq --arg sid "$CURRENT_SID" '.session_id = $sid' "$STATE_FILE" > "$TMP_STATE"; then
      mv "$TMP_STATE" "$STATE_FILE"
    else
      rm -f "$TMP_STATE"
    fi
    echo "{}"; exit 0
  fi
  if [ -n "$STORED_SID" ] && [ -n "$CURRENT_SID" ] && [ "$STORED_SID" != "$CURRENT_SID" ]; then
    # Stored sid differs from current → different session → stale → allow
    echo "{}"; exit 0
  fi
  # Confirmed + same session (or no sid context available) → allow
  echo "{}"; exit 0
fi

# Pending + within TTL + skill=fix-bug + not confirmed → deny
jq -n '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: "Readback required: this fix-bug session has not received user confirmation on the 3-paragraph plain-language echo. Dispatch readback:intent-echoer agent, present output, wait for user to reply \"go\" or correct. Update .claude/readback-state.json user_confirmed=true after confirmation."
  },
  systemMessage: "Write blocked by readback: complete the read-back protocol first."
}'
