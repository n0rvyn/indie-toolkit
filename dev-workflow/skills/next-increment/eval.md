# next-increment Eval

## Trigger Tests
- "What should I do next?" (on a codebase with `docs/02-architecture/`)
- "next-increment"
- "pick the next evolution step"
- "下一步做什么"
- "下一步"

## Negative Trigger Tests
- "Start a new project" → `write-dev-guide`
- "Continue Phase 2" → `run-phase`
- "Plan this task" → `write-plan`
- "Help me design a new feature" (with no architecture docs) → `brainstorm`

## Output Assertions
- [ ] Preconditions check: architecture docs present; no `in_progress` increment
- [ ] 3-5 candidates surfaced, every field (`what`, `what_not`, `verify`, `depends_on`, `signal_velocity`, `reversibility`, `complexity`, `doc_anchors`) filled
- [ ] Candidates span at least 3 archetypes (infrastructure-seed / user-visible / risk-reducer)
- [ ] `Gut pick` and `Reasoned top-1` lines present, stated separately
- [ ] Verify field is concrete (curl / SQL / CLI / UI step), not "manual check"
- [ ] AskUserQuestion fires with 4 options, top-1 labeled "(推荐)"
- [ ] Mini-spec written to `docs/06-plans/YYYY-MM-DD-<slug>-increment.md` with frontmatter
- [ ] `.claude/increment-history.yml` appended (or created) with new entry, `status: pending`
- [ ] Next-skill suggestion stated once, mapped from complexity

## Scenario Tests

### Scenario 1: Mature project with arch docs (happy path)
**Setup:** `docs/02-architecture/*.md` present, no `.claude/increment-history.yml`.
**Expected:**
- Skill gathers context from arch docs + git log + src layout
- Produces 3-5 candidates, archetype-diverse
- User picks one → mini-spec written, history file created with first entry
- Recommends next skill based on complexity

### Scenario 2: No architecture docs (precondition fail)
**Setup:** `docs/02-architecture/` missing or empty.
**Expected:**
- Skill stops before Step 1
- Outputs: "No architecture docs found ... Consider `/brainstorm` or `/write-dev-guide` first."
- No files written, no AskUserQuestion

### Scenario 3: Prior increment still in_progress (precondition fail)
**Setup:** `.claude/increment-history.yml` has an entry with `status: in_progress`.
**Expected:**
- Skill stops before Step 1
- Outputs: "Increment `{id}` ({name}) is still in progress. Finish or mark it `abandoned` before picking a new one."
- No mini-spec written

## Redundancy Risk
Baseline comparison: Base model can propose next steps but does not enforce archetype diversity, concrete verify, or mini-spec persistence. Base model tends to produce one "obvious next thing" rather than 3-5 archetype-diverse candidates.
Last tested model: Opus 4.6
Last tested date: 2026-04-15
Verdict: keep (structural guarantees around diversity, verify concreteness, and mini-spec persistence are not replicable by base model)
