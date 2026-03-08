# testing-guide Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "How do I set up unit tests for my iOS project?"
- "What's the best way to write UI tests?"
- "Explain mocking and dependency injection"
- "如何编写 iOS 测试？"
- "What should my test coverage strategy be?"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Fix this test failure"
- "Review my code"
- "Write a plan"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output identifies testing scenario (unit tests / UI tests / mocking / TDD / coverage)
- [ ] Output greps section markers from testing-guide.md
- [ ] Output reads only the relevant section based on scenario-to-section mapping
- [ ] Unit tests: shows Given-When-Then pattern, naming conventions, setUp/tearDown
- [ ] UI tests: explains recording vs programmatic approaches, accessibility identifiers
- [ ] Mocking: demonstrates protocol-based mocking and DI patterns
- [ ] Output provides interactive guidance rather than static documentation dump

## Redundancy Risk
Baseline comparison: Base model can explain testing concepts but lacks structured reference-based interactive guidance
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
