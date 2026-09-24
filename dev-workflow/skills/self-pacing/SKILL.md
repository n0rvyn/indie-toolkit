---
name: self-pacing
description: "Moved: use /afk (dev-guide mode) to drive a verified dev-guide across phases; for one plan use /execute-plan. Triggers: '/self-pacing', 'self-pace', '跨阶段连跑', '不要每个阶段都停'."
disable-model-invocation: true
---

## Moved

- **Whole dev-guide, across phase seams** → `/afk` (dev-guide mode) now drives it.
- **One phase / one plan** → `/execute-plan`, which already gates per checkpoint.
- **An old session's card** at `.claude/self-pacing/<slug>-handoff.md` whose `Resume with` says `/self-pacing` → type `/afk` instead. Dev-guide mode finds `.claude/dev-workflow-state.json` (the state file is shared), resumes at its `phase_step`, and hands back a `/goal` line to paste. `dev-workflow:handoff` still reads the old card and run log.

See `dev-workflow/skills/afk/SKILL.md` § Dev-guide mode and `dev-workflow/skills/afk/DESIGN-dev-guide-mode.md`.
