# Plugin Quality Baseline Report

**Date:** 2026-03-08
**Model:** Claude Opus 4.6
**Scope:** 6 plugins, 55 skills total

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total skills | 55 |
| Skills with eval.md | 55 |
| Coverage | 100% |
| Plugins reviewed | 5 (claude-api has 0 skills) |
| Total findings | 73 (11 bug, 34 logic, 28 minor) |
| Trigger health: pass | 50 |
| Trigger health: warn | 5 |
| Trigger health: fail | 0 |

---

## Plugin Overview

| Plugin | Skills | Agents | Findings (B/L/M) | Trigger Health (pass/warn) | needs-fix artifacts |
|--------|--------|--------|-------------------|---------------------------|---------------------|
| dev-workflow | 22 | 9 | 5/10/8 | 21 pass, 1 warn | 5 (collect-lesson, fix-bug, reviewing-rules, design-drift-auditor, flow-tracer) |
| ios-development | 17 | 4 | 3/8/7 | 16 pass, 1 warn | 7 (design-review, ui-review, appstoreconnect-review, execution-review, project-kickoff, design-reviewer, feature-reviewer, ui-reviewer) |
| mactools | 10 | 1 | 1/6/5 | 8 pass, 2 warn | 1 (spotlight) |
| product-lens | 5 | 6 | 2/7/5 | 4 pass, 1 warn | 2 (evaluate, teardown) |
| skill-audit | 1 | 1 | 0/3/3 | 1 pass | 0 |
| claude-api | 0 | 0 | N/A | N/A | N/A |

---

## Trigger Health Score by Plugin

### dev-workflow (22 skills)

| Skill | Description Quality | Eval Coverage | Conflict Check | Verdict |
|-------|--------------------|---------------|----------------|---------|
| brainstorm | pass | pass | pass (moderate overlap w/ design-decision) | **pass** |
| collect-lesson | pass | pass | pass | **pass** |
| commit | pass | pass | pass | **pass** |
| crystallize | pass | pass | pass | **pass** |
| design-decision | pass | pass | pass (moderate overlap w/ brainstorm) | **pass** |
| design-drift | pass | pass | pass | **pass** |
| docs-rag | pass | pass | pass | **pass** |
| execute-plan | warn (weak trigger keywords) | pass | warn (overlap w/ run-phase) | **warn** |
| finish-branch | pass | pass | pass | **pass** |
| fix-bug | pass | pass | pass | **pass** |
| generate-design-prompt | N/A (disable-model-invocation) | pass | N/A | **pass** |
| generate-vf-prompt | pass | pass | pass | **pass** |
| handoff | pass | pass | pass | **pass** |
| parallel-agents | pass | pass | pass | **pass** |
| reviewing-rules | N/A (disable-model-invocation) | pass | N/A | **pass** |
| run-phase | pass | pass | pass | **pass** |
| understand-design | pass | pass | pass | **pass** |
| use-worktree | pass | pass | pass | **pass** |
| verify-plan | pass | pass | pass | **pass** |
| write-dev-guide | pass | pass | pass (mitigated by "Not This Skill" section) | **pass** |
| write-feature-spec | pass | pass | pass | **pass** |
| write-plan | pass | pass | pass (mitigated by write-dev-guide's "Not This Skill") | **pass** |

### ios-development (17 skills)

| Skill | Description Quality | Eval Coverage | Conflict Check | Verdict |
|-------|--------------------|---------------|----------------|---------|
| appstoreconnect-review | pass | pass | pass | **pass** |
| design-review | pass | pass | pass | **pass** |
| execution-review | pass | pass | pass | **pass** |
| feature-review | pass | pass | pass | **pass** |
| fetch-swift-api-updates | pass | pass | pass | **pass** |
| generate-design-system | pass | pass | pass | **pass** |
| generate-stitch-prompts | pass | pass | pass | **pass** |
| ios-swift-context | pass | pass | pass (intentionally broad) | **pass** |
| localization-setup | pass | pass | pass | **pass** |
| project-kickoff | pass | pass | pass | **pass** |
| setup-ci-cd | pass | pass | pass | **pass** |
| submission-preview | pass | pass | pass | **pass** |
| swiftdata-patterns | pass | pass | pass | **pass** |
| testing-guide | pass | pass | pass | **pass** |
| ui-review | pass | pass | pass | **pass** |
| update-asc-docs | pass | pass | warn (overlap w/ appstoreconnect-review on "prepare submission") | **warn** |
| validate-design-tokens | pass | pass | pass | **pass** |

### mactools (10 skills)

| Skill | Description Quality | Eval Coverage | Conflict Check | Verdict |
|-------|--------------------|---------------|----------------|---------|
| calendar | pass | pass | pass | **pass** |
| contacts | pass | pass | pass | **pass** |
| mail | pass | pass | pass | **pass** |
| notes | pass | pass | pass | **pass** |
| ocr | pass | pass | pass | **pass** |
| omnifocus | pass | pass | warn (keyword "待办" overlaps w/ reminders) | **warn** |
| photos | pass | pass | pass | **pass** |
| reminders | pass | pass | warn (keyword "待办" overlaps w/ omnifocus) | **warn** |
| safari | pass | pass | pass | **pass** |
| spotlight | pass | pass | pass | **pass** |

### product-lens (5 skills)

| Skill | Description Quality | Eval Coverage | Conflict Check | Verdict |
|-------|--------------------|---------------|----------------|---------|
| compare | pass | pass | pass | **pass** |
| demand-check | pass | warn ("elevator pitch test" ambiguous) | warn (overlap w/ evaluate) | **warn** |
| evaluate | pass | fail (incorrect GO/DEFER/KILL assertion) | pass | **pass** |
| feature-assess | pass | pass | pass | **pass** |
| teardown | pass | pass | pass | **pass** |

### skill-audit (1 skill)

| Skill | Description Quality | Eval Coverage | Conflict Check | Verdict |
|-------|--------------------|---------------|----------------|---------|
| plugin-review | pass | pass | pass | **pass** |

### claude-api (0 skills)

No skills. Plugin provides API integration only.

---

## Key Findings

### Critical Bugs (must fix)

| # | Plugin | Artifact | Issue |
|---|--------|----------|-------|
| 1 | ios-development | design-review, ui-review | Reference paths use `~/.claude/docs/` instead of `references/` — files won't exist for other users |
| 2 | mactools | spotlight | `allowed-tools` doesn't cover direct `mdfind` commands documented in Advanced Usage |
| 3 | product-lens | evaluate/eval.md | Incorrect assertion: claims GO/DEFER/KILL verdict (belongs to feature-assess) |
| 4 | product-lens | teardown | Skips market-scanner for Demand Authenticity despite evaluate providing full market data for it |
| 5 | dev-workflow | fix-bug | References non-existent `EnterPlanMode` tool |
| 6 | dev-workflow | design-drift-auditor, flow-tracer | `Bash` in tools list contradicts read-only Constraint |

### Cross-Skill Conflicts (4 pairs)

| Pair | Plugin | Shared Keyword | Severity | Mitigation |
|------|--------|----------------|----------|------------|
| omnifocus / reminders | mactools | "待办" | warn | Add explicit app-name requirement to descriptions |
| execute-plan / run-phase | dev-workflow | plan execution | warn | Existing differentiation (batch vs phase-guided) is implicit |
| update-asc-docs / appstoreconnect-review | ios-development | "prepare submission" | warn | Both have `disable-model-invocation: true` |
| demand-check / evaluate | product-lens | "elevator pitch test" | warn | Clarify demand-check eval trigger wording |

### Recurring Patterns

1. **Skill-calling-skill** (ios-development: design-review→validate-design-tokens, ui-review→validate-design-tokens, project-kickoff→generate-stitch-prompts/setup-ci-cd) — skills cannot invoke other skills at runtime
2. **Read-only agents with Write tool** (dev-workflow: plan-verifier, implementation-reviewer; ios-development: design-reviewer, feature-reviewer, ui-reviewer) — constraint wording is ambiguous
3. **Cross-plugin agent references without fallback** (dev-workflow: docs-rag→mactools:spotlight-search, ios-development: execution-review→dev-workflow:implementation-reviewer)
4. **Missing README tables** (dev-workflow, ios-development, mactools) — no skills/agents inventory in README

---

## Redundancy Risk Assessment (6 High-Risk Skills)

These skills provide capability uplift that may become redundant as base model capabilities improve.

| Skill | Baseline Comparison | Last Tested | Verdict |
|-------|--------------------|-------------|---------|
| dev-workflow:brainstorm | Base model can brainstorm but lacks structured intent extraction, requirement gathering, and design-before-implementation gate | 2026-03-08 | monitor |
| dev-workflow:design-decision | Base model can compare options but lacks structured trade-off separation (essential vs accidental complexity) and comparison table enforcement | 2026-03-08 | monitor |
| dev-workflow:parallel-agents | Base model can launch parallel agents but lacks structured independence validation and shared-state conflict detection | 2026-03-08 | likely-redundant |
| dev-workflow:use-worktree | Base model can use git worktrees but lacks structured worktree lifecycle management and cleanup guidance | 2026-03-08 | likely-redundant |
| dev-workflow:handoff | Base model can summarize sessions but lacks structured cold-start prompt generation with crystal file integration and plan status extraction | 2026-03-08 | likely-redundant |
| dev-workflow:crystallize | Base model can summarize decisions but lacks structured decision extraction with D-xxx format and plan-writer/verifier integration | 2026-03-08 | monitor |

---

## Recommended Actions

### Priority 1: Fix Bugs
1. Fix ios-development reference paths (`~/.claude/docs/` → `references/`)
2. Fix mactools spotlight `allowed-tools` to cover `mdfind`
3. Fix product-lens evaluate eval.md incorrect assertion
4. Fix product-lens teardown market-scanner exclusion for Demand Authenticity
5. Fix dev-workflow fix-bug `EnterPlanMode` reference
6. Remove `Bash` from dev-workflow read-only agents (design-drift-auditor, flow-tracer)

### Priority 2: Logic Issues
7. Fix ios-development skill-calling-skill pattern (design-review, ui-review, project-kickoff)
8. Disambiguate mactools omnifocus/reminders "待办" overlap
9. Consider upgrading dev-workflow handoff from `model: haiku` to `model: sonnet`
10. Add save-report steps to product-lens compare, teardown, feature-assess

### Priority 3: Documentation
11. Add README tables to dev-workflow, ios-development, mactools
12. Fix product-lens marketplace.json missing "feature assessment"

---

## Appendix: Full Skill Inventory

### dev-workflow (22)
brainstorm, collect-lesson, commit, crystallize, design-decision, design-drift, docs-rag, execute-plan, finish-branch, fix-bug, generate-design-prompt, generate-vf-prompt, handoff, parallel-agents, reviewing-rules, run-phase, understand-design, use-worktree, verify-plan, write-dev-guide, write-feature-spec, write-plan

### ios-development (17)
appstoreconnect-review, design-review, execution-review, feature-review, fetch-swift-api-updates, generate-design-system, generate-stitch-prompts, ios-swift-context, localization-setup, project-kickoff, setup-ci-cd, submission-preview, swiftdata-patterns, testing-guide, ui-review, update-asc-docs, validate-design-tokens

### mactools (10)
calendar, contacts, mail, notes, ocr, omnifocus, photos, reminders, safari, spotlight

### product-lens (5)
compare, demand-check, evaluate, feature-assess, teardown

### skill-audit (1)
plugin-review

### claude-api (0)
No skills.

---

## Methodology

**Trigger Health Score computation:**
- **Description Quality**: pass/warn/fail based on trigger clarity (clear "Use when" scenario, no vague standalone words)
- **Eval Coverage**: pass/fail/N/A (N/A if no eval.md exists)
- **Conflict Check**: pass/warn/fail based on cross-skill trigger overlap detection

**Redundancy Risk Assessment:**
- **essential**: Skill provides capability that base model cannot replicate without tool integration or systematic methodology
- **monitor**: Skill provides value but may become redundant with model improvements; requires periodic re-evaluation
- **likely-redundant**: Skill can likely be replaced by base model with minimal guidance

---

## Next Steps

1. ~~Run `/plugin-review` on all 6 plugins to populate Trigger Health Score tables~~ ✅ Done
2. Address Priority 1 bugs (6 items)
3. Address Priority 2 logic issues (4 items)
4. Schedule quarterly redundancy re-assessment for high-risk skills
5. Update baseline after major model upgrades (e.g., Opus 5.0)
