# swiftdata-patterns Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "How do I define a SwiftData model with relationships?"
- "What's the best way to query SwiftData?"
- "SwiftData migration best practices"
- "SwiftData 并发安全怎么保证？"
- "Help me design my data models"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Fix this SwiftData bug"
- "Review my code"
- "Write a plan"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output identifies user's need (@Model / Relationships / Querying / Migration / Concurrency / Performance / Testing)
- [ ] Output greps section markers from swiftdata-guide.md
- [ ] Output reads only the relevant section based on need-to-section mapping
- [ ] @Model: shows basic pattern, optional vs required, @Transient and @Attribute modifiers
- [ ] Relationships: explains one-to-many, many-to-many patterns
- [ ] Concurrency: explains @ModelActor isolation and main actor boundaries
- [ ] Output provides interactive guidance rather than static documentation dump

## Redundancy Risk
Baseline comparison: Base model can explain SwiftData concepts but lacks structured reference-based interactive guidance with section-targeted loading
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
