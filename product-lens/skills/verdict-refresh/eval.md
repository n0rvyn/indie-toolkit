# verdict-refresh Eval

## Trigger Tests
- "I got new evidence; should I change my decision?"
- "Refresh the verdict for AppA"
- "{\"intent\":\"verdict_refresh\",\"targets\":[\"~/Code/AppA\"],\"evidence_paths\":[\"~/Obsidian/PKOS/.../verdict.md\"]}"

## Negative Trigger Tests
- "Evaluate this project from scratch"
- "Review recent commits only"
- "Write a development plan"

## Output Assertions
- [ ] Output requires or resolves a prior verdict input
- [ ] Output compares old reasons against new evidence
- [ ] Output uses only `unchanged`, `upgraded`, `downgraded`, `reversed`
- [ ] Output publishes refresh exchange artifacts
- [ ] Output returns machine summary first

## Redundancy Risk
Baseline comparison: Base model can revisit an opinion, but lacks explicit delta analysis, prior-verdict comparison, and PKOS-compatible refresh storage
Last tested model: Opus 4.6
Last tested date: 2026-04-12
Verdict: essential
