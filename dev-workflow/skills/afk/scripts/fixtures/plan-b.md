# Plan B — Phase 2 plan (fixture, fully resolved)

### Task 1: Ship the checkpoint-marked task

**Files:**
- `src/build.py`

**Steps:**
1. do it

<!-- checkpoint -->

**Verify:**
Run: `true`
Expected: exit 0.

### Task 2: Ship the follow-on task

**Files:**
- `src/build_more.py`

**Steps:**
1. do it more

**Verify:**
Run: `true`
Expected: exit 0.

## Decisions

### [DP-001] Which build tool? (recommended)

**Context:** already resolved — this fixture must sweep as resolved.
**Options:**
- A: make
- B: ninja
**Chosen:** A — user chose "make" on 2026-09-24.

---
## Verification
- **Verdict:** Approved
- **Date:** 2026-09-24
- **Advisories:** none
