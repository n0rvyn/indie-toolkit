# commit Eval

## Trigger Tests
- "commit"
- "Save my progress"
- "Commit the changes"

## Negative Trigger Tests
- "Push to remote"
- "Create a pull request"

## Output Assertions
- [ ] Output analyzes uncommitted changes with git status/diff
- [ ] Output groups changes logically by concern
- [ ] Diff >= 200 lines, public API changes, removals, or red/yellow Project Health `module_size` trigger MUST dispatch `dev-workflow:review-before-commit` via Skill tool (not inline analysis)
- [ ] Static fixture covers a large/high-risk diff route into review-before-commit before commit grouping (verify the dispatch is hard, not advisory)
- [ ] Output uses conventional commit format (type(scope): description)
- [ ] BREAKING commits use form `<type>(scope)!:` or `<type>!:` (! AFTER scope parens, NOT `<type>!(scope):`)
- [ ] Scope follows plugin-name convention from `references/conventional-commits.md` (e.g., `feat(dev-workflow):` not `feat(sync):` in this monorepo)
- [ ] Types used are from canonical list (feat/fix/docs/refactor/perf/test/chore); `style` is NOT in project's list
- [ ] Pre-commit audit runs before any group is committed
- [ ] Secrets/credential patterns in diff lines are detected and blocked
- [ ] Debug residue (console.log, debugger, breakpoint) in diff lines is detected and blocked
- [ ] TODO/FIXME in diff lines generates warnings (not blocks)
- [ ] Large files (>500KB) are detected and blocked
- [ ] Blocked groups are NOT committed; clean groups proceed
- [ ] Audit findings appear in output with file:line and reason
- [ ] git status clean after all commits completed (or only blocked files remain)

## Redundancy Risk
Baseline comparison: Base model can commit but lacks conventional commit format enforcement, logical grouping methodology, and pre-commit safety audit
Last tested model: haiku 4.5
Last tested date: 2026-03-08
Verdict: monitor
