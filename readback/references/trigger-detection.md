# Trigger Detection — when readback fires

## Hook chain (user-prompt-submit.sh)

Detection order (first match wins for skip; otherwise fall through to action-verb match):

### Skip 1: Orchestration commands
Regex: `^/(run-phase|execute-plan|verify-plan|commit|test-changes|finalize|reload-plugins|exit|clear)( |$)`
Why: These are flow-control, not action requests.

### Skip 2: Trivial-edit verbs
Regex (case-insensitive): `\b(rename|reformat|format|import organize|remove unused|move (this|that) (file|code))\b`
Why: These are the 5 categories CLAUDE.md exempts from "陈述预期" rule.

### Skip 3: Question-only prompts
Starts with interrogative AND no action verb:
- Interrogative: `^(what|how|why|when|where|does|can|is|should|will|怎么|为什么|什么是|是不是)\b`
- Action verb (presence vetoes skip): `\b(fix|implement|write|build|create|refactor|add|change|update|修|改|实现|重构|加|写)\b`

### Skip 4: Explicit bypass
Regex: `^(go|直接做|just do it|--no-questions|skip readback)\b`

### Action-verb match (the trigger)

ASCII regex (case-insensitive, with `\b` word boundaries):
```
\b(fix|implement|refactor|build|create.*(feature|component|module|hook|skill|agent|plugin)|write.*(code|implementation|function|class|method)|change.*(behavior|logic|implementation|code|api)|update.*(implementation|function|module|behavior|logic))\b
```

CJK regex (no word boundaries — BSD grep `\b` doesn't work with multibyte chars):
```
(修|实现|重构|写代码)
```

Note: bare `create` / `write` / `change` / `update` without a qualifier do NOT trigger (too broad). Compound forms required (`create a feature`, `write code`, `change behavior`, `update implementation`, etc.). Bare CJK `改` / `加` also do NOT trigger as standalone single-character matches — they would generate too many false positives on prompts like `改名`/`加注释`. Only the compound CJK verbs listed above fire the mandate.

## Skill-level trigger
- `/fix-bug` always triggers (hard mode, via Step pre-0)
- `/write-plan` triggers in Step 2.5 unless caller is run-phase (soft mode)
- `/readback` itself is the manual entry

## State-based suppression (active confirmed readback)
If `.claude/readback-state.json` has `user_confirmed=true`:
- `UserPromptSubmit` hook reads state directly and suppresses the mandate when stored `session_id` is null OR matches stdin `session_id` (same session). The hook cannot distinguish "same logical task" from "new logical task within the same session" — once any readback is confirmed in a session, action-verb prompts in that session do not re-fire the mandate. Cross-session (stored sid differs from stdin sid) → mandate fires again.
- If you want a fresh readback within a confirmed session, manually reset state: `rm .claude/readback-state.json` or invoke `/readback` to overwrite.
