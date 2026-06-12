---
type: plan
status: active
contract_version: 2
---

# Plan Pair Boundary (Test Fixture)

**Goal:** A `Task 5-tests` / `Task 5-impl` pair positioned so a naive batch-of-5 cut would land between them; pair-keep rule must keep them in the same batch.

## Impact Map

**Touched surface:** none.

---

### Task 1: First task

**Files:**
- Create: `pair/a.txt`

**Steps:**
1. Create a.txt

**Verify:**
Run: `test -f pair/a.txt`
Expected: exit 0

### Task 2: Second task

**Files:**
- Create: `pair/b.txt`

**Steps:**
1. Create b.txt

**Verify:**
Run: `test -f pair/b.txt`
Expected: exit 0

### Task 3: Third task

**Files:**
- Create: `pair/c.txt`

**Steps:**
1. Create c.txt

**Verify:**
Run: `test -f pair/c.txt`
Expected: exit 0

### Task 4: Fourth task

**Files:**
- Create: `pair/d.txt`

**Steps:**
1. Create d.txt

**Verify:**
Run: `test -f pair/d.txt`
Expected: exit 0

### Task 5-tests: Tests for task 5

**Files:**
- Create: `pair/5_test.txt`

**Steps:**
1. Create test file

**Verify:**
Run: `test -f pair/5_test.txt`
Expected: exit 0

### Task 5-impl: Impl for task 5

**Files:**
- Create: `pair/5_impl.txt`

**Steps:**
1. Create impl file

**Verify:**
Run: `test -f pair/5_impl.txt`
Expected: exit 0

### Task 6: Sixth task (after the pair)

**Files:**
- Create: `pair/f.txt`

**Steps:**
1. Create f.txt

**Verify:**
Run: `test -f pair/f.txt`
Expected: exit 0
