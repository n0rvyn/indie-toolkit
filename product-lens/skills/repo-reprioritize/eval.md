# repo-reprioritize Eval

## Trigger Tests
- "Which project should I focus on next?"
- "Reprioritize my repos under ~/Code"
- "{\"intent\":\"repo_reprioritize\",\"project_root\":\"~/Code\"}"

## Negative Trigger Tests
- "How is AppA progressing?"
- "Review recent feature commits"
- "Evaluate this single app in depth"

## Output Assertions
- [ ] Output uses only `focus`, `maintain`, `freeze`, `stop`
- [ ] Output includes biggest blockers and next actions per project
- [ ] Output publishes verdict exchange artifacts
- [ ] Output returns machine-readable summary first

## Redundancy Risk
Baseline comparison: Base model can rank projects, but lacks stable verdict storage, PKOS exchange publication, and repeatable reprioritization language
Last tested model: Opus 4.6
Last tested date: 2026-04-12
Verdict: essential
