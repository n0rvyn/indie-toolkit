# TDD Research: 2026 Coding-Agent Findings

**Purpose**

`write-plan`'s Task Contract already requires verify-first per Pocock TDD. This reference documents 2026 research findings on TDD-with-coding-agent failure modes and mitigation patterns, to back that rule with empirical evidence.

---

## What Current Research Shows

TDD is the strongest single agentic-coding pattern in 2026 benchmarks, but single-context TDD has documented failure modes that degrade agentic coding quality. AgentCoder (Dec 2023) demonstrated that multi-agent test generation raises pass@1 from 67% to 96.3%, and that structured test generation raises accuracy from 61% to 87.8% on held-out test cases. Single-context TDD (one agent writing both tests and implementation in the same context) is the primary risk vector for these failure modes.

---

## Failure Modes Table

| Failure Mode | Mechanism | Observable Signature | Mitigation |
|---|---|---|---|
| **Implementation-first bias** | Agent writes implementation before tests; tests then confirm the implementation, not the spec | Tests pass but cover only the implementation's assumptions; edge cases are missing | Plan-time test-impl split (separate tasks) |
| **Implementation-first bias** | Agent writes implementation before tests; tests then confirm the implementation, not the spec | Tests pass but cover only the implementation's assumptions; edge cases are missing | Plan-time test-impl split (separate tasks) |
| **Test tampering** | Agent modifies tests during implementation to make them pass rather than fixing the implementation | Tests pass after impl, but tests are different from what was originally committed | Regression shield on Task N-tests; committed-test checkpoint |
| **Context pollution** | Test assertions leak implementation details from the impl-writer agent back into the test (overfitting) | Tests assert on internal function names, call counts, or specific implementation patterns | Plan-time split isolates test-writer context |
| **Verification gap** | Agent marks task "done" without running tests; tests may be broken | `test-changes` reports failure only at end-of-plan; no mid-plan signal | PostToolUse hooks auto-run tests after each task |
| **Overfitting** | Tests encode specific implementation choices rather than user-observable behavior | Tests pass but break when equivalent impl is tried; tests are fragile | Plan-time split + test-fidelity audit |

---

## 2026 Mitigation Stack

### (a) Plan-time test-impl split

`write-plan` generates two separate tasks when a conceptual task would naturally produce both test files and implementation files. This isolates the test-writer agent's context from the implementer's via the plan structure itself.

- **Task N-tests**: Files list contains only test files. Automated verify asserts tests COMPILE and FAIL.
- **Task N-impl**: Files list contains only implementation files. Automated verify asserts tests now PASS. Includes `**Regression shield:**` prohibiting test modification.

This is the mitigation implemented in this codebase (per DP-001 Option B).

### (b) Multi-agent context isolation

General principle underlying (a): separate agent contexts prevent context pollution via multi-agent isolation. Even without a formal multi-agent system, plan structure achieves the same isolation via context boundaries between tasks.

### (c) PostToolUse hooks for auto-running tests

Hooks automatically execute tests after each task edit, catching failures before the next task starts.

### (d) Committed-test checkpoint pattern

Tests are committed (written and not modified) before implementation begins. The implementation must make the committed tests pass, not the other way around.

### (e) verify-suite as separate phase

`test-changes` skill runs the full test suite after plan execution completes, as a separate phase. This is the empirical layer; plan-time split and committed-test checkpoint are the structural layer.

---

## When TDD Applies vs When to Skip

**Apply TDD (default):**
- Non-trivial business logic (algorithms, data transformations, validation)
- Multi-file changes with integration points
- New API endpoints or service boundaries

**Skip TDD:**
- Trivial edits: typo corrections, log-line additions, variable renames with no behavior change
- Configuration changes (`.md`, `.yml`, `.json`) with no logic
- Refactors with no behavior change (tests should pass before AND after; verify-first ordering doesn't apply)

For non-trivial work, default to verify-first. The `Automated verify` line must be writable BEFORE the implementation exists and must be able to FAIL (no false-pass via missing-file errors).

---

## Relationship to SDD (Spec-Driven Development)

SDD (Spec-Driven Development) wraps TDD: the spec is the primary artifact, and tests are generated outputs from the spec. This is distinct from TDD's test-first approach.

GitHub Spec Kit and Kiro (2025-2026) are representative SDD tools: they generate test scaffolding from a specification document, treating the spec as the source of truth rather than hand-written tests.

dev-workflow's `write-plan` Task Contract already acts as a lightweight spec layer: the `Expected behavior` field is the spec, and the `Automated verify` line is the generated test artifact. The plan-time split (Task N-tests + Task N-impl) is the structural equivalent of SDD's test generation step.

---

## Sources

- implementation-first, test tampering, context pollution, verification gap, overfitting: see failure modes table above
- Multi-agent isolation: see § 2026 mitigation stack (b)
- Committed-test checkpoint: see § 2026 mitigation stack (d)
- AgentCoder 96.3% pass@1: AgentCoder research (Dec 2023)
- [TDD with Large Language Models — Steve Kinney](https://stevekinney.io)
- [AI-Assisted Test-Driven Development — Alex Eves](https://alexop.dev)
- [Test-Driven Development in the Age of AI — The BCMS](https://thebcms.com)
- [AI and Test-Driven Development — DataCamp](https://datacamp.com)
- [Software Development in the Age of AI — The New Stack](https://thenewstack.io)
- [Agentic TDD: How I Ship Better Code with AI Coding Agents — Nathan Fox](https://nathanfox.net)
- [AI Coding Agents: The Future of Developer Productivity — Build This Now](https://buildthisnow.com)
- [Claude Best Practices: Test-Driven Development](https://code.claude.com/docs/en/best-practices)

---

## How dev-workflow Skills Consume This Reference

| Skill / Step | Section Read | Purpose |
|---|---|---|
| `write-plan` Step 1 (Pre-flight Audit) | § Failure modes table | Task Structure callout: surfaces test tampering and verification gap risks |
| `write-plan` Writing Guideline 12 | § 2026 mitigation stack (a) | Plan-time test-impl split rule |
| `write-plan` Task Structure callout | § Failure modes table | FAIL-first rule backed by research evidence |
| `execute-plan` Step 2 | § 2026 mitigation stack (a) | Documentation note: why some plans contain N-tests + N-impl pairs |
| `implementation-reviewer` agent | § Failure modes table ("test tampering", "overfitting") | Test-fidelity audit for split task pairs (Task 8) |
