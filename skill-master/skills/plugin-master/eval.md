# plugin-master Eval

## Trigger Tests
- "plugin-master"
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
- "run insights on dev-workflow"
- "auto-tune my skills based on usage"
- "/plugin-master insights --window 30"
- "propose improvements from real usage data"

## Negative Trigger Tests
- "review my code" (→ code review, not plugin review)
- "create a PR" (→ git workflow)
- "design review" (→ apple-dev design review)
- "build my app" (→ general development)
- "write a plan" (→ dev-workflow write-plan)
- "audit the CLAUDE.md rules" (→ dev-workflow audit-rules)
- "commit my changes" (→ dev-workflow commit)
- "brainstorm a feature" (→ dev-workflow brainstorm)
- "show me my git log usage" (→ git/shell tool, NOT insights — insights is about Claude Code session usage)
- "improve verify-plan" (→ iterate, NOT insights — iterate works on a specific named skill; insights works on aggregate evidence)

## Output Assertions
- [ ] Routes to correct workflow based on intent (create/review/iterate/package/insights)
- [ ] Ambiguous input prompts user to choose route
- [ ] create: dispatches intent-distiller for structured intent extraction
- [ ] create: delegates to plugin-dev for component creation
- [ ] create: delegates to skill-creator for eval loop (when creating skills)
- [ ] create: auto-triggers review after creation
- [ ] create: quality gate presented (pass/needs-fix)
- [ ] review: produces 9-dimension report
- [ ] review: Strategy A/B routing based on plugin-dev availability
- [ ] review: includes cross-plugin trigger conflict section via trigger-arbiter
- [ ] review: findings grouped by severity (Bug/Logic/Minor)
- [ ] iterate: classifies issue type (trigger/logic/eval/agent)
- [ ] iterate: uses skill-creator run_loop.py for description optimization
- [ ] iterate: compares to baseline when available
- [ ] package: validates marketplace readiness for full plugin
- [ ] package: supports single component injection into target project
- [ ] package: uses skill-creator package_skill.py when available
- [ ] insights: preflight passes (db / schema / marketplace / gh CLI all OK)
- [ ] insights: dispatches proposer agent with single JSON payload matching schema
- [ ] insights: validate_proposal rejects forbidden changes (frontmatter / Process section / deletions)
- [ ] insights: dispatches judge agent for semantic accumulation check (DP-V1=D)
- [ ] insights: judge dispatch failure → deny-all (conservative default)
- [ ] insights: opens draft PR via pr_composer OR exits 0 with actionable reason

## Redundancy Risk
Baseline comparison: orchestrates plugin-dev + skill-creator
Last tested model: (not yet tested)
Verdict: essential
