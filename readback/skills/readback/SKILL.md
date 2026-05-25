---
name: readback
description: "Use when the user says '/readback', 'readback', 'echo my intent', 'restate my ask', 'play it back', '复述', '复述一下', '回读'. Triggers a manual 3-paragraph plain-language echo of the user's current intent via the intent-echoer agent — before substantial code/plan work, or to recover alignment after drift. '/readback status' shows current readback state. Not when: inside /brainstorm Step 2 (its Expectation Recap handles alignment via '对齐了'). Not when: a plan file already exists and user wants it validated (use /verify-plan). Not when: post-code review (use /review-execution). Not when: user wants a code or doc summary (use Read/Grep directly). Not when: user wants progress summary for next session (use /handoff). Not when: user wants to extract decisions from past discussion (use /crystallize or /distill-discussion)."
user-invocable: true
allowed-tools: Bash(jq:*, mkdir:*, date:*, mv:*, rm:*), Task
---

# Readback

Manual read-back protocol. Restates user intent in plain language via the `intent-echoer` agent. Use before substantial code/plan changes, or to recover alignment after drift.

## Process

### Path A: `/readback status`

If args is `status` or empty + user explicitly asks for state:
1. Check `.claude/readback-state.json`
2. If absent: report "No readback state — fresh session"
3. If present: show: session_id, skill (or null), readback_done, user_confirmed, confirmed_at, correction_count, created_at
4. STOP. Do not dispatch agent.

### Path B: `/readback` (no args, or with intent text)

1. Collect input for `intent-echoer`:
   - `user_request`: from args if provided, else from the most recent user turn in the conversation (the previous user message before this `/readback` invocation)
   - `draft_plan`: if a plan file is referenced in recent conversation or visible at `docs/06-plans/`, include its Goal + Architecture sections (read first 30 lines)
   - `context_terms`: extract 3-5 project-specific terms used by the user in this session (from last 10 user messages)

2. Dispatch `readback:intent-echoer` agent with the inputs above. Use Task tool with `subagent_type: "readback:intent-echoer"`, model is set by agent frontmatter.

3. When agent returns:
   - Present the agent's output VERBATIM to the user. Do not paraphrase. Do not add framing like "Here's what I think you want:". The agent's output IS the message.
   - Do NOT proceed to other work in this turn.

4. Write `.claude/readback-state.json`:

   First, capture the agent's verbatim output into a shell variable. **Substitute the literal content between the EOF markers with the actual text returned by intent-echoer** — do not modify, escape, or summarize. **Always use a unique random suffix on the EOF marker** (e.g., `EOF_AGENT_OUTPUT_A7F3B2`) to eliminate any collision risk if the agent output happens to contain the literal marker string. Pick a 6-character hex nonce each time; use the same suffix on both opening and closing markers.

   ```bash
   AGENT_OUTPUT=$(cat <<'EOF_AGENT_OUTPUT_A7F3B2'
   {paste the intent-echoer agent's literal output between the EOF markers — do not modify}
   EOF_AGENT_OUTPUT_A7F3B2
   )
   ```

   Then write state:
   ```bash
   mkdir -p .claude
   jq -n \
     --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     --arg text "$AGENT_OUTPUT" \
     '{
       created_at: $ts,
       session_id: null,
       skill: null,
       readback_done: true,
       readback_text: $text,
       user_confirmed: false,
       confirmed_at: null,
       correction_count: 0
     }' > .claude/readback-state.json
   ```

5. STOP. Wait for user response:
   - User says "go" / "OK" / "对" / "yes" → update state with confirmation:
     ```bash
     jq --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
       '.user_confirmed = true | .confirmed_at = $ts' \
       .claude/readback-state.json > .claude/readback-state.json.tmp \
       && mv .claude/readback-state.json.tmp .claude/readback-state.json
     ```
     Then yield control back (do not auto-proceed to anything).
   - User says "不对" / "wrong" / corrects → re-dispatch intent-echoer with the correction, capture new output as `AGENT_OUTPUT`, then increment correction_count:
     ```bash
     jq --arg text "$AGENT_OUTPUT" \
       '.readback_text = $text | .correction_count += 1' \
       .claude/readback-state.json > .claude/readback-state.json.tmp \
       && mv .claude/readback-state.json.tmp .claude/readback-state.json
     ```
     Present new agent output verbatim. If `correction_count` reaches 2: STOP, suggest `/brainstorm` (alignment problem is upstream), AND mark state as bailed-out so subsequent action prompts in this session don't loop the failing readback:
     ```bash
     jq --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
       '.user_confirmed = true | .confirmed_at = $ts | .bail_reason = "max_corrections"' \
       .claude/readback-state.json > .claude/readback-state.json.tmp \
       && mv .claude/readback-state.json.tmp .claude/readback-state.json
     ```
     (Setting `user_confirmed = true` lets the user-prompt-submit.sh state-aware short-circuit suppress further mandates; the `bail_reason` field documents why. State will naturally expire via the 30-min TTL on `confirmed_at`.)
   - User asks something unrelated → leave state as-is (readback unresolved); do not silently treat as confirmation.

## Completion criteria

- intent-echoer dispatched, output presented verbatim
- state file written with v2 schema (`created_at` set; `session_id: null`; `confirmed_at: null` initially)
- user has responded ("go", correction, or unrelated)
