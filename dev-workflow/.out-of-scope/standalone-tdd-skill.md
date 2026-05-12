# Standalone /tdd skill

**Decision:** Do not add a separate `/tdd` skill modelled on `mattpocock/skills` `tdd/SKILL.md`.
**Rejected on:** 2026-05-09
**Reason:** Our `write-dev-guide` already enforces vertical slicing at the phase level, and `write-plan` Task Contract enforces "Verifiable signal first, Steps satisfy it" at the task level. A dedicated `/tdd` skill would duplicate guarantees already provided by the planning surface and add a third entry point users have to remember. Pocock's TDD ideas were absorbed structurally into `write-plan` Task Structure (see `dev-workflow/skills/write-plan/SKILL.md` § Task Structure).
**Reopen condition:** If users repeatedly bypass the Task Contract (e.g., write Steps before filling in verify lines) AND a dedicated `/tdd` skill would change that behavior, reconsider.
