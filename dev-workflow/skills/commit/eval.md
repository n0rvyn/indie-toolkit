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
- [ ] Output uses conventional commit format (type(scope): description)
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
