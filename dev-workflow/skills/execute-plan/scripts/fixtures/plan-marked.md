---
type: plan
status: active
contract_version: 2
---

# Plan Marked (Test Fixture)

**Goal:** A non-hub batch has an explicit `<!-- checkpoint -->` marker, so that batch is a hard-stop.

## Impact Map

**Touched surface:** none.

---

### Task 1: First task

**Files:**
- Create: `marked/a.txt`

**Steps:**
1. Create a.txt

**Verify:**
Run: `test -f marked/a.txt`
Expected: exit 0

<!-- checkpoint -->

### Task 2: Second task

**Files:**
- Create: `marked/b.txt`

**Steps:**
1. Create b.txt

**Verify:**
Run: `test -f marked/b.txt`
Expected: exit 0

### Task 3: Third task

**Files:**
- Create: `marked/c.txt`

**Steps:**
1. Create c.txt

**Verify:**
Run: `test -f marked/c.txt`
Expected: exit 0

### Task 4: Fourth task

**Files:**
- Create: `marked/d.txt`

**Steps:**
1. Create d.txt

**Verify:**
Run: `test -f marked/d.txt`
Expected: exit 0

### Task 5: Fifth task

**Files:**
- Create: `marked/e.txt`

**Steps:**
1. Create e.txt

**Verify:**
Run: `test -f marked/e.txt`
Expected: exit 0
