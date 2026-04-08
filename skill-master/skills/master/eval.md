# master Eval

## Trigger Tests
- "master"
- "build a plugin that monitors stale PRs"
- "create a new skill for code review"
- "create an agent that validates configs"
- "review the dev-workflow plugin"
- "audit my plugin"
- "the trigger on my commit skill is too broad"
- "improve this skill's trigger quality"
- "iterate on the brainstorm skill"
- "package this as a standalone skill"
- "export this plugin for marketplace"
- "inject this skill into my other project"

## Negative Trigger Tests
- "review my code" (→ code review, not plugin review)
- "create a PR" (→ git workflow)
- "design review" (→ apple-dev design review)
- "build my app" (→ general development)
- "write a plan" (→ dev-workflow write-plan)
- "audit the CLAUDE.md rules" (→ dev-workflow audit-rules)
- "commit my changes" (→ dev-workflow commit)
- "brainstorm a feature" (→ dev-workflow brainstorm)

## Output Assertions
- [ ] Routes to correct workflow based on intent (create/review/iterate/package)
- [ ] Ambiguous input prompts user to choose route
- [ ] create: dispatches intent-distiller for structured intent extraction
- [ ] create: delegates to plugin-dev for component creation
- [ ] create: delegates to skill-creator for eval loop (when creating skills)
- [ ] create: auto-triggers review after creation
- [ ] create: quality gate presented (pass/needs-fix)
- [ ] review: produces 9-dimension report matching skill-audit format
- [ ] review: Strategy A/B routing based on plugin-dev availability
- [ ] review: includes cross-plugin trigger conflict section via trigger-arbiter
- [ ] review: findings grouped by severity (Bug/Logic/Minor)
- [ ] iterate: classifies issue type (trigger/logic/eval/agent)
- [ ] iterate: uses skill-creator run_loop.py for description optimization
- [ ] iterate: compares to baseline when available
- [ ] package: validates marketplace readiness for full plugin
- [ ] package: supports single component injection into target project
- [ ] package: uses skill-creator package_skill.py when available

## Redundancy Risk
Baseline comparison: subsumes skill-audit:plugin-review, orchestrates plugin-dev + skill-creator
Last tested model: (not yet tested)
Verdict: essential
