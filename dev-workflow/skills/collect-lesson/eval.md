# collect-lesson Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Collect a lesson from this session about the bug we fixed"
- "Save what we learned about SwiftData concurrency to the knowledge base"
- "Extract an error entry from this debugging session"
- "记录这个 bug 的教训到知识库"
- "把刚才发现的架构约束保存为 lesson"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Fix this bug"
- "Write a plan for the new feature"
- "Review my code"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output extracts Symptom, Root Cause, and Prevention from the session
- [ ] Output asks user to confirm draft before saving
- [ ] Output includes category slug and 3-6 keywords
- [ ] Output reports saved entry id and path after completion
- [ ] Graceful degradation prints draft if add_entry unavailable

## Redundancy Risk
Baseline comparison: Base model can summarize sessions but lacks structured extraction, duplicate checking, and RAG integration
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
