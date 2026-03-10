# kb Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Search the knowledge base for SwiftData concurrency issues"
- "Find past lessons about streaming API pitfalls"
- "kb volcengine"
- "在知识库里搜索设计漂移相关的内容"
- "Have we seen this CoreML issue before?"
- "Search for architecture decisions about agent dispatch"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Create a new feature"
- "Fix this bug"
- "Save this lesson" (should trigger /collect-lesson instead)
- "Write a plan"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output searches ~/.claude/knowledge/ via Grep (not MCP)
- [ ] Output presents results grouped by file with category, date, and keywords
- [ ] Output offers to read full files
- [ ] Zero results suggests broader keywords and /collect-lesson
- [ ] Zero results falls back to project-local docs/09-lessons-learned/
- [ ] Category filter narrows search path when specified

## Redundancy Risk
Baseline comparison: Base model can Grep files but lacks the convention of where knowledge lives and how to present results
Last tested model: Opus 4.6
Last tested date: 2026-03-10
Verdict: essential
