# verify-plan Eval

## Trigger Tests
- "Verify this plan before I start coding"
- "Check the plan for issues"
- "review plan 检查计划"

## Negative Trigger Tests
- "Write a new plan for this feature"
- "Execute the plan now"

## Output Assertions
- [ ] Output includes verdict: Approved | Must-revise
- [ ] Output includes falsifiable error candidates tested
- [ ] Must-revise items include specific revision instructions
- [ ] Previously resolved decisions (Chosen: in plan) are not re-asked
- [ ] Dispatch prompt template must reference dev-workflow/.out-of-scope/ archive directory.
- [ ] `contract_version: 1` plans missing `Impact Map` or `Task Contract` fields are must-revise
- [ ] Legacy plans without `contract_version` receive a warning rather than a hard failure for missing contract fields

- [ ] Frontmatter marks this skill `user-invocable: false` while keeping model routing available
- [ ] Internal route phrases trigger this skill without user slash-command wording

## Contract Fixtures

### Fail: contract v1 without Task Contract

```markdown
---
type: plan
status: active
contract_version: 1
---

## Impact Map
**User path:** X
**Data path:** X
**Shared surfaces:** X
**Existing consumers:** X
**Must remain unchanged:** X
**Regression checks:** X

### Task 1: API Change
**Touched surface:** API
**Regression shield:** existing tests
```

### Pass: contract v1 with Impact Map and Task Contract

```markdown
---
type: plan
status: active
contract_version: 1
---

## Impact Map
**User path:** X
**Data path:** X
**Shared surfaces:** X
**Existing consumers:** X
**Must remain unchanged:** X
**Regression checks:** X

### Task 1: API Change
**Expected outcome:** invalid requests fail.
**Non-goals:** no UI changes.
**Touched surface:** API.
**Regression shield:** valid request fixture.
**Task Contract:**
- Automated verify: route test.
- Real path verify: curl route.
- Manual/device verify: none.
```

## Redundancy Risk
Baseline comparison: Base model can review plans but lacks Verification-First methodology with falsifiable assertions
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
