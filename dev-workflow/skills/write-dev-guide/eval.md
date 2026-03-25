# write-dev-guide Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Write a development guide for this project"
- "Create a phased plan for implementing this design"
- "生成一个分阶段的开发指南"
- "Break down this project into phases"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Write a plan for this single feature"
- "Brainstorm design options"
- "Fix this bug"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output gathers design doc, project brief, and architecture docs before dispatching
- [ ] Output stops and informs user if no design doc exists (suggests running project-kickoff first)
- [ ] Output dispatches dev-guide-writer agent with all gathered context
- [ ] Output dispatches dev-guide-verifier agent after writer completes (Step 2.7)
- [ ] If verifier finds revision-needed: V7 issues are fixed directly, V1-V6 issues trigger writer re-dispatch
- [ ] If verifier produces Decisions: they are merged with dev-guide Decisions in Step 3
- [ ] Output presents Phase outline as a table with Goal and Dependencies
- [ ] Output presents Decision Points via AskUserQuestion for blocking decisions
- [ ] Output asks user to confirm or adjust structure before proceeding
- [ ] Output presents per-phase confirmation table with user-visible changes, key files, acceptance criteria

## Redundancy Risk
Baseline comparison: Base model can outline projects but lacks standardized phased structure and design-doc anchoring
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
