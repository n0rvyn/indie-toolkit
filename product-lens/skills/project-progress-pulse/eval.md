# project-progress-pulse Eval

## Trigger Tests
- "How are these projects progressing?"
- "Give me a progress pulse on AppA and AppB"
- "{\"intent\":\"project_progress_pulse\",\"targets\":[\"~/Code/AppA\"]}"

## Negative Trigger Tests
- "Which project should I focus on next?"
- "Should I build this proposed feature?"
- "Compare Bear and Notion"

## Output Assertions
- [ ] Output focuses on observable progress indicators
- [ ] Output never uses fake completion percentages
- [ ] Output uses only `accelerating`, `steady`, `stalled`, `drifting`
- [ ] Output writes PKOS exchange artifacts
- [ ] Output returns machine summary first

## Redundancy Risk
Baseline comparison: Base model can describe repo activity, but not with a stable progress vocabulary and PKOS-compatible exchange contract
Last tested model: Opus 4.6
Last tested date: 2026-04-12
Verdict: essential
