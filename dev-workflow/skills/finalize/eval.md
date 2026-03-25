# finalize Eval

## Trigger Tests
- "finalize"
- "final check"
- "cross-phase validation"
- "all phases done, validate"
- "run final validation"

## Negative Trigger Tests
- "run phase"
- "finish branch"
- "review implementation"
- "write plan"

## Output Assertions
- [ ] Checks all phases complete before proceeding (or offers override)
- [ ] Runs full test suite with 0 fail, 0 skip requirement
- [ ] Blocks on test failures — does not proceed
- [ ] Verifies acceptance criteria across all completed phases
- [ ] Audits cumulative test coverage from all plan files
- [ ] Identifies shell tests (exist but no assertions)
- [ ] Scans for untested source files
- [ ] Produces persistent report in .claude/reviews/
- [ ] Reports verdict with next action suggestion

## Redundancy Risk
Baseline comparison: finish-branch verifies tests pass but does not check cross-phase criteria or cumulative coverage; implementation-reviewer checks per-phase plan-vs-code but not cross-phase regression
Last tested model: (not yet tested)
Last tested date: (not yet tested)
Verdict: essential
