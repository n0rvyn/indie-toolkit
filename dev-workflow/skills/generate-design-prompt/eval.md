# generate-design-prompt Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Generate a Stitch prompt for the main screen"
- "Create a design prompt for Figma based on my code"
- "生成一个设计工具的 prompt 来描述这个界面"
- "Make a refine prompt from the design analysis feedback"
- "Create prompts for all screens in the app"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Write a plan for this feature"
- "Analyze this design screenshot"
- "Fix this bug"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output detects available design tools (Stitch/Figma MCP) and suggests target
- [ ] Output extracts product positioning, target users, core features from project docs
- [ ] Output generates UI zone breakdown for each screen with layout, data display, states, interactions
- [ ] Output supports multiple modes: initial generation, refinement from analysis feedback, all-screens batch
- [ ] Output is formatted for copy-paste into external design tools (Stitch/Figma)

## Redundancy Risk
Baseline comparison: Base model can describe UIs but lacks systematic extraction from code and translation to design tool prompt language
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
