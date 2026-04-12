# recent-feature-review Eval

## Trigger Tests
- "Review the recent features in AppA"
- "How do the last two weeks of commits look?"
- "{\"intent\":\"recent_feature_review\",\"targets\":[\"~/Code/AppA\"],\"window_days\":14}"

## Negative Trigger Tests
- "Should I add AI chat to this app?"
- "Which project should I focus on next?"
- "Fix this regression"

## Output Assertions
- [ ] Output inspects a recent commit window
- [ ] Output groups changes into likely feature slices
- [ ] Output uses only `double_down`, `polish`, `simplify`, `rethink`, `drop`
- [ ] Output publishes feature-review exchange artifacts
- [ ] Output returns machine summary before Markdown

## Redundancy Risk
Baseline comparison: Base model can comment on commits, but lacks feature-slice clustering, normalized recommendation vocabulary, and PKOS exchange publication
Last tested model: Opus 4.6
Last tested date: 2026-04-12
Verdict: essential
