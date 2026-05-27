# distill-project-skills Eval

## Trigger Tests
- "distill skills from this project"
- "mine project patterns"
- "找重复模式"
- "看哪些值得做成 skill"
- "提炼项目 skill"
- "挖项目模式"
- "scan recent sessions for skill candidates"
- "what should I crystallize as a new skill"

## Negative Trigger Tests
- "extract decisions from this discussion file" (→ distill-discussion)
- "tune the description of my existing audit-tokens skill" (→ skill-master insights)
- "save the design decisions before we plan" (→ crystallize)
- "write a postmortem for this bug" (→ collect-lesson)
- "audit my token spend last week" (→ audit-tokens)
- "create a skill called codebase-search" (→ plugin-dev:skill-development directly; distill is for IDENTIFYING which skills to build, not building a known one)
- "review my plugin" (→ plugin-master review route)

## Output Assertions
- [ ] `/tmp/distill-candidates.json` exists with `candidates[]` and `meta` keys
- [ ] Each candidate has fields: pattern, frequency, est_cost_usd, suggested_name, suggested_frontmatter, status
- [ ] `status` is one of: new, name-exists, possibly-covered, already-built
- [ ] Patterns with `outcome=declined` in history within 30 days are filtered out (not in candidates)
- [ ] User is asked AskUserQuestion for selection (no autonomous creation)
- [ ] If informational rows exist, user gets a SECOND AskUserQuestion for override
- [ ] For each accepted candidate, plugin-dev:skill-development is dispatched (not plugin-master)
- [ ] After each creation, verify_frontmatter.py is run; mismatch → Edit; re-verify
- [ ] `${PROJECT}/.claude/distill-history.jsonl` gets one entry per candidate presented (outcome: created/declined/error)
- [ ] `${PROJECT}/.claude/cost-hint.log` is archived ONLY at the end (Step 6), after creation loop completes
- [ ] If skill is interrupted mid-flow (Step 5 errors), cost-hint.log is preserved (not archived)
- [ ] Final summary lists created/declined/errored/informational counts

## Routing-Conflict Coverage
- Distinct from `distill-discussion` (file-based input vs session-telemetry-based)
- Distinct from `crystallize` (records decisions vs identifies skill gaps)
- Distinct from `skill-master:plugin-master insights` (improves existing skills vs identifies missing ones)
- Distinct from `audit-tokens` (aggregates spend vs surfaces creation candidates)

## Redundancy Risk
Baseline comparison: Base model can identify repeated work in transcripts but cannot:
  - Quantify per-pattern frequency across multiple session files
  - Cross-check candidates against installed skill inventory (994+ SKILL.md files)
  - Maintain 30-day declined memory across sessions
  - Enforce cost-posture frontmatter via verify_frontmatter.py
Last tested model: Opus 4.7
Last tested date: 2026-05-27
Verdict: keep
