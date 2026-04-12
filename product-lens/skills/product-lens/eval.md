# product-lens Eval

## Trigger Tests
- "Is this idea worth pursuing?"
- "Should I build this feature?"
- "Which project should I focus on?"
- "I got new evidence; should I change my decision?"
- "{\"intent\":\"portfolio_scan\",\"project_root\":\"~/Code\",\"mode\":\"summary\",\"save_report\":true,\"sync_notion\":false}"

## Negative Trigger Tests
- "Fix this bug"
- "Write the implementation for this screen"
- "Run tests for this package"

## Output Assertions
- [ ] Routes idea questions to `demand-check`
- [ ] Routes single-product deep evaluations to `evaluate`
- [ ] Routes proposed-feature decisions to `feature-assess`
- [ ] Routes multi-project periodic work to portfolio-oriented skills
- [ ] AI-facing responses include a machine-readable summary envelope before long-form Markdown
- [ ] PKOS boundary is stated: exchange artifacts first, final vault placement later

## Redundancy Risk
Baseline comparison: Base model can answer product questions directly but lacks stable route selection, AI entry contract, and PKOS boundary awareness across `product-lens` workflows
Last tested model: Opus 4.6
Last tested date: 2026-04-12
Verdict: essential
