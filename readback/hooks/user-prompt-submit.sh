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
if echo "$PROMPT" | grep -qE "^/(run-phase|execute-plan|verify-plan|commit|test-changes|finalize|reload-plugins|exit|clear|fork-this)( |$)"; then
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

# Skip 5: discussion / opinion / brainstorm request (matches anywhere in prompt,
# not just at start). These are conversational signals that the user wants
# analysis or agreement, not code/plan execution. False-positive guard against
# the CJK presence-match action-verb detector below (e.g., "修修补补" as metaphor).
#
# NOTE: `理解` deliberately omitted from the `你(...)` alternation. The phrase
# "你理解错了" appears in correction loops (user telling the model that the
# previous readback missed the point) and is often followed by an action verb
# like "重新理解 + 修 X". Suppressing mandate there would silently skip the
# re-readback the user actually wants. The intentional `/readback` invocation
# phrasing `你理解了吗` was removed from the skill description for the same
# reason (too generic; user can use explicit triggers like `/readback` instead).
if echo "$PROMPT" | grep -qE "你(同意|觉得|认为|怎么看|怎么想)" \
   || echo "$PROMPT" | grep -qE "如何(更好|改进|优化|设计|做|解决|处理|应对)" \
   || echo "$PROMPT" | grep -qE "我(觉得|认为|的看法|的认识|在想|想问|想了解)" \
   || echo "$PROMPT" | grep -qE "(同意我|同意吗|觉得呢|对吗)[？?。.]?" \
   || echo "$PROMPT" | grep -qiE "(do you agree|what do you think|how would you|think (carefully|step.by.step|hard))"; then
  echo "{}"; exit 0
fi

# Strip idiomatic non-action expressions that contain action-verb morphemes.
# These are metaphors/nouns, not action requests, but BSD grep without \b for
# CJK cannot distinguish them positionally. Filter before the verb regex runs.
# Portable across locales (sed byte-level substitution).
PROMPT_FILTERED=$(printf '%s' "$PROMPT" \
  | sed -e 's/修修补补//g' \
        -e 's/缝缝补补//g' \
        -e 's/打补丁//g' \
        -e 's/补丁式//g' \
        -e 's/这个实现//g' \
        -e 's/那个实现//g' \
        -e 's/它的实现//g' \
        -e 's/他的实现//g' \
        -e 's/某种实现//g')

# Detect action verbs (the trigger condition)
# ASCII path uses \b; CJK path uses presence-match (no \b — BSD grep limitation)
if echo "$PROMPT_FILTERED" | grep -qiE "\b(fix|implement|refactor|build|create.*(feature|component|module|hook|skill|agent|plugin)|write.*(code|implementation|function|class|method)|change.*(behavior|logic|implementation|code|api)|update.*(implementation|function|module|behavior|logic))\b" \
   || echo "$PROMPT_FILTERED" | grep -qE "(修|实现|重构|写代码)"; then
  # State-aware short-circuit: skip mandate when readback is already confirmed
  # for the current session (covers both pre-stamp and post-stamp windows).
  STATE_FILE=".claude/readback-state.json"
  if [ -r "$STATE_FILE" ]; then
    STORED_SID=$(jq -r '.session_id // empty' "$STATE_FILE" 2>/dev/null || echo "")
    # Normalize v1 schema residue: treat "unknown" identically to null
    [ "$STORED_SID" = "unknown" ] && STORED_SID=""
    CURRENT_SID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null || echo "")
    CONFIRMED=$(jq -r '.user_confirmed // false' "$STATE_FILE" 2>/dev/null || echo "false")
    CONFIRMED_AT=$(jq -r '.confirmed_at // empty' "$STATE_FILE" 2>/dev/null || echo "")
    # Confirmed → suppress mandate when either:
    # (a) stored sid matches current stdin sid (same session, post-stamp), or
    # (b) stored sid is empty BUT confirmation is fresh (< 30 min) — the
    #     pre-stamp window between user 'go' confirmation and the first
    #     Write/Edit that triggers pre-tool-use.sh stamping.
    # Different stored vs current sid → fall through (different session, re-prompt).
    # Empty stored sid + expired confirmation → fall through (state leaked from
    # an old session where pre-tool-use.sh never stamped, e.g., skill != fix-bug
    # or no Write/Edit ever ran). The 30-min TTL matches pre-tool-use.sh phase 1.
    if [ "$CONFIRMED" = "true" ]; then
      if [ -n "$STORED_SID" ] && [ "$STORED_SID" = "$CURRENT_SID" ]; then
        echo "{}"; exit 0
      fi
      if [ -z "$STORED_SID" ] && [ -n "$CONFIRMED_AT" ]; then
        # macOS BSD date vs GNU date fallback chain (mirrors pre-tool-use.sh).
        # Date-parse failure → silent fall-through (fail-closed): the inner `if`
        # never executes, the outer state-short-circuit block falls out, and
        # mandate injection proceeds. Safer than fail-open (which would
        # silently trust a corrupt confirmed_at value and suppress mandate).
        if NOW_TS=$(date -u +%s 2>/dev/null) \
           && CONF_TS=$( (date -j -u -f "%Y-%m-%dT%H:%M:%SZ" "$CONFIRMED_AT" +%s 2>/dev/null) \
                         || (date -d "$CONFIRMED_AT" +%s 2>/dev/null) ); then
          AGE=$((NOW_TS - CONF_TS))
          if [ "$AGE" -ge 0 ] && [ "$AGE" -lt 1800 ]; then
            echo "{}"; exit 0
          fi
        fi
      fi
    fi
  fi

  # Inject readback mandate
  # NOTE: When triggered by this hook (vs `/readback`), the SKILL.md is NOT
  # auto-loaded into the main session. The mandate text below is the ONLY
  # guidance the main model receives, so the "paste verbatim into message
  # body" rule must be spelled out here (Step 3 of SKILL.md alone is not
  # visible on this path). See indie-toolkit readback-skill QA 2026-05-25.
  #
  # FORMAT NOTE: the heredoc body contains nested triple-backtick fences
  # (correct/incorrect format examples). Single-quoted heredoc (<<'MANDATE_EOF')
  # preserves them literally; jq --arg ctx serializes the full multi-line
  # string into the JSON additionalContext value. Verified to render correctly
  # in the model's system-instruction view.
  MANDATE=$(cat <<'MANDATE_EOF'
[readback-mandate] Before writing any plan or code in this turn:

1. Task-dispatch the `readback:intent-echoer` agent with the user prompt as input.

2. PASTE the agent's full output verbatim INTO YOUR REPLY MESSAGE BODY (the text you send to the user). Do NOT only say "回读已发出" / "readback dispatched" and rely on the collapsed tool-result panel — users cannot see tool results without manually expanding them, so the agent's 3-paragraph output MUST appear in your message text. The agent's output IS your message.

3. After the verbatim paste, add ONE short line asking the user to confirm. Then STOP and wait.

Correct format (do this):
```
{verbatim 3-paragraph agent output, unmodified, no preamble}

按 mandate 等你确认。回「go」/「直接做」我就展开；理解偏了告诉我哪里偏。
```

Incorrect (do NOT do this — agent output missing from message body):
```
按 readback mandate, 先把意图回读给你确认。
[readback:intent-echoer dispatched — Done · 29.6k tokens · 24s]
回读已发出，等你确认或修正。
```

If the user replies "go" / "直接做" / "OK" / similar, you may proceed with the original task; if they correct you, revise and re-dispatch intent-echoer with the correction. Skip this mandate only if you are inside an orchestration skill (/run-phase, /execute-plan) or the user has already confirmed a readback in this session for the SAME request chain.
MANDATE_EOF
)
  jq -n --arg ctx "$MANDATE" '{
    hookSpecificOutput: {
      hookEventName: "UserPromptSubmit",
      additionalContext: $ctx
    }
  }'
  exit 0
fi

# Default: pass-through
echo "{}"
