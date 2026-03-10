# generate-stitch-prompts Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Generate a Stitch prompt for the main screen"
- "Create a prompt for Google Stitch based on my code"
- "生成一个 Stitch prompt 来描述这个界面"
- "Generate prompts for all screens"
- "Make a follow-up prompt for the settings screen"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Write a plan for this feature"
- "Analyze this design"
- "Fix this bug"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output automatically gathers project context from CLAUDE.md, design docs, UI components, types, styles, router
- [ ] Output extracts screen inventory with name, function, zones, key interactions
- [ ] Output decomposes target screen into UI zones: layout, data display, states, inputs, actions, feedback, navigation
- [ ] Output generates Stitch prompt describing "what UI looks like and what user can do" (no backend implementation)
- [ ] Output supports parameterized targets: empty=main screen, screen name, all for batch generation
- [ ] Output is formatted for copy-paste into Stitch

## Redundancy Risk
Baseline comparison: Base model can describe UIs but lacks systematic extraction from code and translation to Stitch prompt language
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
