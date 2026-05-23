# handoff Eval

## Trigger Tests
- "handoff"
- "Session is running low on context"
- "Continue this in a new session"

## Negative Trigger Tests
- "Commit my changes"
- "Write a summary"
- "Fork this topic to a separate session" (should route to /fork-this — mid-session orthogonal split, not end-of-session full transfer)
- "Park this for later" (should route to /fork-this)

## Output Assertions
- [ ] Output generates cold-start prompt for session transfer
- [ ] Output includes decision history and pending tasks
- [ ] Output is model-agnostic (haiku can generate)
- [ ] Absolute file paths included for key files
- [ ] Key code snippets pasted for context

## Redundancy Risk
Baseline comparison: Base model can summarize context but lacks structured cold-start prompt format for session continuity
Last tested model: haiku 4.5
Last tested date: 2026-03-08
Verdict: likely-redundant
