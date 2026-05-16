#!/usr/bin/env bash
# readback: user-prompt-submit — detect action verbs and inject mandate
# Schema v2: state-aware short-circuit when readback already confirmed in this session.
set -e

# Fail-open on any unexpected error
trap 'echo "{}"; exit 0' ERR

INPUT=$(cat)
# NOTE: Claude Code stdin field is `prompt` (not `user_prompt`); verified
# against dev-workflow/hooks/suggest-skills.sh in this repo.
PROMPT=$(echo "$INPUT" | jq -r '.prompt // empty')

[ -z "$PROMPT" ] && { echo "{}"; exit 0; }

# Skip conditions (highest priority — fast exit)
# Skip 1: orchestration commands
if echo "$PROMPT" | grep -qE "^/(run-phase|execute-plan|verify-plan|commit|test-changes|finalize|reload-plugins|exit|clear)( |$)"; then
  echo "{}"; exit 0
fi

# Skip 2: trivial-edit verbs (rename / format / import / dead-code / move)
if echo "$PROMPT" | grep -qiE "\b(rename|reformat|format|import organize|remove unused|move (this|that) (file|code))\b"; then
  echo "{}"; exit 0
fi

# Skip 3: question-only prompts (interrogative, no action)
# Note: BSD grep \b doesn't work with multibyte CJK chars; CJK arms have no \b.
if echo "$PROMPT" | grep -qiE "^(what|how|why|when|where|does|can|is|should|will)\b" \
   || echo "$PROMPT" | grep -qE "^(怎么|为什么|什么是|是不是)"; then
  # but only skip if no action verb follows
  if ! echo "$PROMPT" | grep -qiE "\b(fix|implement|write|build|create|refactor|add|change|update)\b" \
     && ! echo "$PROMPT" | grep -qE "(修|改|实现|重构|加|写)"; then
    echo "{}"; exit 0
  fi
fi

# Skip 4: explicit bypass
if echo "$PROMPT" | grep -qiE "^(go|just do it|--no-questions|skip readback)\b" \
   || echo "$PROMPT" | grep -qE "^直接做"; then
  echo "{}"; exit 0
fi

# Detect action verbs (the trigger condition)
# ASCII path uses \b; CJK path uses presence-match (no \b — BSD grep limitation)
if echo "$PROMPT" | grep -qiE "\b(fix|implement|refactor|build|create.*(feature|component|module|hook|skill|agent|plugin)|write.*(code|implementation|function|class|method)|change.*(behavior|logic|implementation|code|api)|update.*(implementation|function|module|behavior|logic))\b" \
   || echo "$PROMPT" | grep -qE "(修|实现|重构|写代码)"; then
  # State-aware short-circuit: skip mandate when readback is already confirmed
  # for the current session (covers both pre-stamp and post-stamp windows).
  STATE_FILE=".claude/readback-state.json"
  if [ -r "$STATE_FILE" ]; then
    STORED_SID=$(jq -r '.session_id // empty' "$STATE_FILE" 2>/dev/null || echo "")
    # Normalize v1 schema residue: treat "unknown" identically to null
    [ "$STORED_SID" = "unknown" ] && STORED_SID=""
    CURRENT_SID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null || echo "")
    CONFIRMED=$(jq -r '.user_confirmed // false' "$STATE_FILE" 2>/dev/null || echo "false")
    # Confirmed → suppress mandate when either:
    # (a) stored sid is empty (not yet stamped by PreToolUse — happens in the
    #     window between user 'go' confirmation and first Write/Edit; we trust
    #     the confirmation regardless of stamping state), or
    # (b) stored sid matches current stdin sid (same session, post-stamp).
    # Different stored vs current sid → fall through (different session, re-prompt).
    if [ "$CONFIRMED" = "true" ]; then
      if [ -z "$STORED_SID" ] || [ "$STORED_SID" = "$CURRENT_SID" ]; then
        echo "{}"; exit 0
      fi
    fi
  fi

  # Inject readback mandate
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: "[readback-mandate] Before writing any plan or code in this turn, you must Task-dispatch the `readback:intent-echoer` agent with the user prompt as input. Verbatim present its 3-paragraph output to the user, then STOP and wait for confirmation. If the user replies \"go\" / \"直接做\" / similar, you may proceed; if they correct you, revise and re-echo. Skip this mandate only if you are inside an orchestration skill (/run-phase, /execute-plan) or the user has already confirmed a readback in this session for the SAME request chain."
    }
  }'
  exit 0
fi

# Default: pass-through
echo "{}"
