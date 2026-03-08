# feature-review Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Review the user journey for this feature"
- "Check if the feature is complete from user perspective"
- "产品审查，看看用户旅程是否完整"
- "Feature review after implementation"
- "Did I miss any edge cases in the user flow?"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Review my code quality"
- "Design review"
- "Write a plan"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output identifies feature spec from docs/05-features/, dev-guide, or user description
- [ ] Output loads project-brief.md for target users and core values context
- [ ] Output maps User Stories to code entry points (buttons, navigation, gestures)
- [ ] Output detects user journey dead ends (navigation push without pop, sheet without dismiss)
- [ ] Output checks empty states, loading states, error states
- [ ] Output verifies feedback for every user action
- [ ] Output complements ui-review (code compliance) and design-review (visual quality)

## Redundancy Risk
Baseline comparison: Base model can review features but lacks systematic user journey tracing from spec to code entry points
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
