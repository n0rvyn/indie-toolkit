# docs-rag Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Search the knowledge base for SwiftData best practices"
- "Find docs about design tokens"
- "Query the RAG index for concurrency patterns"
- "在知识库里搜索设计漂移相关的内容"
- "Search for lessons about git rebase"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Create a new feature"
- "Fix this bug"
- "Write a plan"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output presents RAG search results with source_path, section, score, line_range, and preview
- [ ] Output offers to read full sections for each result
- [ ] Output falls back to Spotlight search if RAG returns no results
- [ ] Output falls back to local Grep/Glob if Spotlight also returns no results
- [ ] Fallback results are clearly labeled as lower relevance than RAG

## Redundancy Risk
Baseline comparison: Base model cannot search external knowledge bases without RAG tool integration; this skill provides the interface
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
