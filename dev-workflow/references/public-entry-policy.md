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

`dev-workflow` manual entries:
- `audit-rules`
- `generate-design-prompt`
- `handoff`


`apple-dev` daily entries for the follow-up task:
- `project-kickoff`
- `design-parity-build`
- `asc-submit-preview`
- `asc-listing`
