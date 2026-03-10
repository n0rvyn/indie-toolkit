# generate-design-system Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Generate a design system from our primary color"
- "Create SwiftUI design tokens following Apple HIG"
- "生成一套完整的 Design System 代码"
- "Generate design system code with OKLCH colors"
- "Create component styles from token specs"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Design a new UI"
- "Review my code"
- "Write a plan"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output reads Apple HIG token reference sections (spacing system, OKLCH color generation)
- [ ] Output derives color palette from primary color using OKLCH conversion
- [ ] Output applies color relationship rules (complementary/analogous/triadic)
- [ ] Output assigns semantic roles via proportion rule (60-30-10 or 80-15-5)
- [ ] Output generates complete design token code for platform (iOS/macOS/both)
- [ ] Output optionally generates component styles if generateComponents=true

## Redundancy Risk
Baseline comparison: Base model can write design tokens but lacks systematic OKLCH derivation from primary color and Apple HIG compliance
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
