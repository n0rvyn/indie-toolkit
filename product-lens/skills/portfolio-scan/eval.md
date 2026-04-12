# portfolio-scan Eval

## Trigger Tests
- "Scan all projects under ~/Code and tell me what looks alive"
- "Run a portfolio scan on my repos"
- "Periodic root-level project scan"
- "{\"intent\":\"portfolio_scan\",\"project_root\":\"~/Code\",\"mode\":\"summary\"}"

## Negative Trigger Tests
- "Should I build this feature?"
- "Evaluate this one product in depth"
- "Fix this bug"

## Output Assertions
- [ ] Output discovers candidate repositories from a root directory or explicit targets
- [ ] Output gathers facts through `repo-activity-scanner`
- [ ] Output uses only normalized portfolio decisions: `focus`, `maintain`, `freeze`, `stop`, `watch`
- [ ] Output writes exchange artifacts through `ingress-publisher`
- [ ] Output returns a machine-readable summary before Markdown

## Redundancy Risk
Baseline comparison: Base model can summarize a folder, but lacks a stable portfolio vocabulary, PKOS exchange boundary, and repeated-scan contract
Last tested model: Opus 4.6
Last tested date: 2026-04-12
Verdict: essential
