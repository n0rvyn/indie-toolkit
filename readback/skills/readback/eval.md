# readback Eval

## Trigger Tests
- "/readback"
- "readback please"
- "复述一下你的理解"
- "对齐一下"
- "让我看看你理解得对不对"
- "echo my intent"

## Negative Trigger Tests
- "fix the bug" (→ handled by user-prompt-submit hook injecting a mandate string — model dispatches intent-echoer directly; not the /readback skill)
- "review my code" (→ /review-execution)
- "/run-phase" (→ orchestration, skip readback)
- "rename this variable" (→ trivial, skip)

## Output Assertions
- [ ] Output dispatches intent-echoer agent (not direct LLM generation)
- [ ] Agent output is presented verbatim (no AI paraphrasing on top)
- [ ] state file `.claude/readback-state.json` is written with `session_id: null` (skills cannot read hook stdin; the PreToolUse hook stamps the real sid on first read after user confirmation per v2 schema)
- [ ] If user replies "go", state.user_confirmed becomes true
- [ ] If user replies with correction, correction_count increments and re-echo happens
- [ ] /readback status path does NOT dispatch agent; just reports state

## Redundancy Risk
Without this skill, users have no direct way to trigger manual realignment mid-conversation.
Verdict: essential entry point for the plugin.
