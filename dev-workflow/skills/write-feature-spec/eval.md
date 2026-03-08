# write-feature-spec Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Write a feature spec for this feature"
- "Generate documentation for what we just built"
- "Create a spec for cross-session context"
- "为这个功能写一份特性文档"
- "Document this feature for the changelog"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Write a plan for this feature"
- "Review my code"
- "Brainstorm design options"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output resolves feature identity from branch name, recent commits, or user input before dispatching
- [ ] Output gathers design docs, dev-guide, and key implementation files
- [ ] Output dispatches feature-spec-writer agent with all context
- [ ] Output handles "no design source" by asking user for design doc path or description
- [ ] Output presents spec summary with User Story status counts and deviation list
- [ ] Output presents Decision Points via AskUserQuestion and records user choices in spec file
- [ ] Output offers follow-up actions: context recovery, changelog use, external review dispatch

## Redundancy Risk
Baseline comparison: Base model can write feature descriptions but lacks systematic deviation detection against design docs and user journey mapping
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
