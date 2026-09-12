# plugin-master Eval

Cases: `evals/plugin-master/` — run from the repo root with `claude plugin eval ./skill-master --tag plugin-master --no-publish`. Trigger tests, negative trigger tests, the create route's intent-distiller dispatch, the slash-invoked insights route's first read, and "improve verify-plan" not taking the insights route live there; this file keeps only what a sandboxed run cannot observe.

## Output Assertions
Not observable: interactive, cross-plugin, host-env
- [ ] Routes to correct workflow based on intent (create/review/iterate/package/insights)
- [ ] Ambiguous input prompts user to choose route
- [ ] create: delegates to plugin-dev for component creation
- [ ] create: probes `claude plugin eval --help`; when unavailable, reports it with the Claude Code version instead of skipping silently
- [ ] create: writes both eval sides per eval-rules.md (`evals/<skill>/` cases or `NOTE.md`, and `eval.md` in pointer / mixed / spec form) and runs the `--max-cost-usd 0` load check
- [ ] create: asks before any eval run beyond the load check, stating case count and flags
- [ ] create: auto-triggers review after creation
- [ ] create: quality gate presented (pass/needs-fix)
- [ ] review: produces 9-dimension report
- [ ] review: Strategy A/B routing based on plugin-dev availability
- [ ] review: passes eval sources (`evals/<skill>/` + `eval.md`) to plugin-reviewer
- [ ] review: includes cross-plugin trigger conflict section via trigger-arbiter
- [ ] review: findings grouped by severity (Bug/Logic/Minor)
- [ ] iterate: classifies issue type (trigger/logic/eval/agent)
- [ ] iterate: builds the skill-creator eval set with the `query` key, from cases first
- [ ] iterate: uses skill-creator run_loop.py for description optimization
- [ ] iterate: re-runs the eval tier matching what changed and compares `aggregate-result.json` with the previous run
- [ ] package: validates marketplace readiness for full plugin, including the Eval layout row
- [ ] package: supports single component injection into target project
- [ ] package: uses skill-creator package_skill.py when available
- [ ] insights: preflight passes (db / schema / marketplace / gh CLI all OK)
- [ ] insights: dispatches proposer agent with single JSON payload matching schema
- [ ] insights: validate_proposal rejects forbidden changes (frontmatter / Process section / deletions)
- [ ] insights: dispatches judge agent for semantic accumulation check (DP-V1=D)
- [ ] insights: judge dispatch failure → deny-all (conservative default)
- [ ] insights: opens draft PR via pr_composer OR exits 0 with actionable reason

## Redundancy Risk
Not observable: interactive, cross-plugin
Baseline comparison: orchestrates plugin-dev + skill-creator + claude plugin eval
Last tested model: (not yet tested)
Verdict: essential
