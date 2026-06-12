---
type: plan
status: active
contract_version: 2
---

# Plan Linear (Test Fixture)

**Goal:** 5 tasks with no hubs, no markers, no pairs.

## Impact Map

**Touched surface:** none.

---

### Task 1: First task

**Files:**
- Create: `foo/a.txt`

**Steps:**
1. Create a.txt

**Verify:**
Run: `test -f foo/a.txt`
Expected: exit 0

### Task 2: Second task

**Files:**
- Create: `foo/b.txt`

**Steps:**
1. Create b.txt

**Verify:**
Run: `test -f foo/b.txt`
Expected: exit 0

### Task 3: Third task

**Files:**
- Create: `foo/c.txt`

**Steps:**
1. Create c.txt

**Verify:**
Run: `test -f foo/c.txt`
Expected: exit 0

### Task 4: Fourth task

**Files:**
- Create: `foo/d.txt`

**Steps:**
1. Create d.txt

**Verify:**
Run: `test -f foo/d.txt`
Expected: exit 0

### Task 5: Fifth task

**Files:**
- Create: `foo/e.txt`

**Steps:**
1. Create e.txt

**Verify:**
Run: `test -f foo/e.txt`
Expected: exit 0
