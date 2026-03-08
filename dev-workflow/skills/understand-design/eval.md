# understand-design Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Analyze this design prototype from Stitch"
- "Understand this Figma design and tell me how to implement it"
- "Review this design screenshot and extract requirements"
- "分析这个设计原型的实现要点"
- "Validate this prototype against the design doc"

## Negative Trigger Tests
<!-- Prompts that SHOULD NOT trigger this skill -->
- "Create a design"
- "Write a plan for this feature"
- "Review my code"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output auto-detects mode (pipeline vs standalone) by searching for design docs with UX Assertions
- [ ] Output acquires design artifacts from multiple sources (Stitch MCP, Figma MCP, manual file paths)
- [ ] Output determines channel availability (dual/image-only/code-only) based on acquired artifacts
- [ ] Output detects tech stack from CLAUDE.md or file extensions
- [ ] Output dispatches design-analyzer agent with correct mode and channel parameters
- [ ] Pipeline mode: output validates prototype against design doc UX assertions
- [ ] Standalone mode: output provides implementation guidance from design analysis

## Redundancy Risk
Baseline comparison: Base model can describe designs but lacks multi-modal acquisition pipeline and design-doc validation mode
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
