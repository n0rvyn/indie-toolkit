# write-plan Eval

## Trigger Tests
- "Create a plan for implementing user authentication"
- "I have a spec and need implementation steps"
- "Write an implementation plan for this feature"

## Negative Trigger Tests
- "Fix this bug in the login flow"
- "Review my existing plan"

## Output Assertions
- [ ] Output includes plan file path at docs/06-plans/
- [ ] Plan has task structure with Files/Steps/Verify sections per task
- [ ] Plan frontmatter includes `contract_version: 2` (new plans; v1 still legal but warns once)
- [ ] Plan includes `## Impact Map`
- [ ] Each non-doc task includes `Expected outcome`, `Touched surface`, `Regression shield`, and `Task Contract`
- [ ] Task template has `**Task Contract:**` block above `**Steps:**` block (TDD-style vertical-slice ordering)
- [ ] `**Task Contract:**` block's first sub-line is `Expected behavior:` (user-visible outcome, 1–3 jargon-free sentences); the Steps reminder cites both `Task Contract.Expected behavior` and `Task Contract.Automated verify`
- [ ] Each non-doc task references at least one Impact Map row via `**Maps to Impact Map:**` field (required for contract_version: 2; advisory for v1)
- [ ] Red/yellow Project Health signals are included in the plan header when scanner output is available
- [ ] Static plugin compliance eval checks dev-workflow/apple-dev frontmatter against the public-entry visibility matrix
- [ ] Static plugin compliance eval checks stale direct `/execution-review` user-routing references are absent from hook/template/verifier/README
- [ ] Step 1 Gather Context must include item 12: out-of-scope archive read with surfacing-to-user behavior on match.
- [ ] Step 1 item 8 Pre-flight Audit references dev-workflow/references/deep-modules-pattern.md for module-shape scan (shallow / adapter / locality signals), with declarative-UI caveat
- [ ] Task Structure section contains the "On the verify-first ordering" callout pointing to dev-workflow/references/tdd-research-2026.md
- [ ] Existing line "vertical slice per Pocock TDD" remains present in Task Structure section (regression: do not remove)
- [ ] Decision points presented if any ambiguities exist

## Contract Fixtures

### Pass: contract v1 task

```markdown
---
type: plan
status: active
contract_version: 1
tags: [example]
refs: []
---

## Impact Map
**User path:** user saves settings
**Data path:** form -> validator -> storage
**Shared surfaces:** settings API
**Existing consumers:** settings screen
**Must remain unchanged:** cancel action
**Regression checks:** focused save/cancel tests

### Task 1: Settings Validation
**Expected outcome:** invalid form cannot save.
**Non-goals:** no layout changes.
**Touched surface:** UI, storage.
**Regression shield:** cancel path test.
**Task Contract:**
- Automated verify: run focused test.
- Real path verify: open settings and try save.
- Manual/device verify: none.
```

### Fail: missing contract fields

```markdown
### Task 1: Do Work
**Files:** Modify: `app.py`
**Steps:** edit file
**Verify:** run grep
```

## Redundancy Risk
Baseline comparison: Base model can write plans but lacks structured task breakdown with verification gates
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
