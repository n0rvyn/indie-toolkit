# Plan A — Phase 1 plan (fixture)

### Task 1: Do the foundational thing

**Files:**
- `src/foundation.py`

**Steps:**
1. do it

**Verify:**
Run: `true`
Expected: exit 0.

## Decisions

### [DP-001] Which storage backend? (blocking)

**Context:** unresolved on purpose — this fixture must sweep as open.
**Options:**
- A: sqlite
- B: flat files
**Recommendation:** A — simpler.

### [DP-002] Log verbosity default? (recommended)

**Context:** unresolved on purpose — this fixture must sweep as open.
**Options:**
- A: info
- B: debug
**Recommendation:** A — quieter default.
