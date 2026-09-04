# Public Entry Policy

Claude Code skill visibility is controlled by `SKILL.md` frontmatter.

| Category | User-visible entry | Model auto-invocation | Frontmatter |
|---|---|---|---|
| `entry-auto` | yes | yes | omit both flags, or `user-invocable: true`; do not set `disable-model-invocation: true` |
| `entry-manual` | yes | no | `disable-model-invocation: true`; omit `user-invocable` or set it to `true` |
| `internal-auto` | no | yes | `user-invocable: false`; do not set `disable-model-invocation: true` |
| `disabled-compat` | no | no | `user-invocable: false` and `disable-model-invocation: true` |

Policy for this pass:
- Preserve every existing skill directory and source name.
- Reduce the daily user entry list by hiding dispatcher/review helpers from the user entry list.
- Keep hidden helpers available for orchestrators and model routing.
- Do not use `disabled-compat` in this pass.

`dev-workflow` daily entries:
- `fix-bug`
- `write-plan`
- `write-dev-guide`
- `run-phase`
- `commit`
- `review-before-commit`
- `issue`
- `finish-branch`
- `execute-plan` (also auto-invoked by `run-phase`; kept user-visible for direct re-runs after manual fixes)
- `handoff` (moved from manual 2026-08-26, commit `1c70b5b`: model-invocation is load-bearing for the AFK path — "keep going, handoff if you hit a real block" with no `/self-pacing` typed has nothing governing it, so without description-match routing nothing fires at the block. Also invoked as a callee by `self-pacing` at terminal STOPs.)

`dev-workflow` manual entries:
- `audit-rules`
- `generate-design-prompt`
- `afk` (goal-oriented unattended driver — walking away and suppressing stops must be a deliberate user choice, never model-routed. Invokes `handoff` as a callee at every stop.)
- `self-pacing` (superseded by `afk`; kept for verified multi-phase dev-guide runs. Same rule: deliberate user choice, never model-routed)


`apple-dev` daily entries for the follow-up task:
- `project-kickoff`
- `design-parity-build`
- `asc-submit-preview`
- `asc-listing`
