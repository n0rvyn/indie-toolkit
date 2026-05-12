# Task Contract Reference

Task Contract makes each plan task explicit before implementation starts.

## Required Plan-Level Impact Map

Every `contract_version: 1` plan includes:

```markdown
## Impact Map
**User path:** What user-visible flow changes.
**Data path:** What data moves from source to destination.
**Shared surfaces:** Shared modules, APIs, docs, hooks, agents, or skills affected.
**Existing consumers:** Known callers/readers/users of the changed surface.
**Must remain unchanged:** Adjacent behavior that is out of scope.
**Regression checks:** Checks that prove adjacent surfaces still work.
```

## Required Task Fields

Every non-doc task includes:

```markdown
**Expected outcome:** Concrete behavior after the task.
**Non-goals:** Explicit things not changed by the task.
**Touched surface:** Files, APIs, data, UI, hooks, or docs changed.
**Regression shield:** What prevents adjacent damage.

**Task Contract:**
- Automated verify: deterministic command or fixture.
- Real path verify: real user/API/tool path, when applicable.
- Manual/device verify: required only when tools cannot verify it.
```

## Examples

### UI change

- Expected outcome: The settings save button stays disabled until required fields are valid.
- Non-goals: No navigation or theme changes.
- Touched surface: `SettingsView`, validation state.
- Regression shield: Existing cancel path remains enabled.
- Automated verify: focused view-state test.
- Real path verify: launch settings and inspect enabled/disabled state.

### API change

- Expected outcome: `POST /tasks` rejects missing `requirements`.
- Non-goals: No role selection UI changes.
- Touched surface: HTTP handler, schema, tests.
- Regression shield: Existing valid task creation fixture still passes.
- Automated verify: route tests.
- Real path verify: `curl` invalid and valid payloads.

### Bug fix

- Expected outcome: Original repro no longer fails.
- Non-goals: No unrelated refactor.
- Touched surface: failing function and direct callers.
- Regression shield: consumer grep and focused regression test.
- Automated verify: regression test.
- Real path verify: replay the original repro path.

### Refactor

- Expected outcome: Same behavior through a smaller internal structure.
- Non-goals: No user-visible behavior change.
- Touched surface: internal modules and callers.
- Regression shield: characterization tests before structural edits.
- Automated verify: characterization and focused unit tests.
- Real path verify: representative command/API still returns same output.

### Docs-only or config-only

Docs-only tasks can skip real path verification when they do not change runtime behavior. They still state:

```markdown
**Regression shield:** Docs-only; no runtime consumer.
**Task Contract:**
- Automated verify: grep or markdown structure check.
- Real path verify: not applicable; docs-only.
- Manual/device verify: none.
```
