# validate-design-tokens Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Validate design tokens in my SwiftUI code"
- "Check if I'm using spacing tokens correctly"
- "验证 Design Token 合规性"
- "Am I using hardcoded colors instead of tokens?"
- "Check for deprecated SwiftUI APIs"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Design review for visual quality"
- "Write a plan"
- "Fix this bug"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output checks deployment target and skips iOS 18+ checks if target < 18.0
- [ ] Output detects deprecated APIs: .cornerRadius(, .foregroundColor(, NavigationView
- [ ] Output flags spacing values not using 8pt multiples or Design System tokens
- [ ] Output identifies hardcoded colors (Color(hex:), Color(red:green:blue:))
- [ ] Output checks font usage uses dynamic type not hardcoded sizes
- [ ] Output flags corner radius not using tokens
- [ ] Output produces compliance report with file:line references and suggested fixes

## Redundancy Risk
Baseline comparison: Base model can spot hardcoded values but lacks systematic token compliance scanning across multiple dimensions
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
