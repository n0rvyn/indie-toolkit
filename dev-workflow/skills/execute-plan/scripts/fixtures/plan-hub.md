---
type: plan
status: active
contract_version: 2
---

# Plan Hub (Test Fixture)

**Goal:** A task with 3+ downstream dependents, so the batch containing the hub becomes a hard-stop at K=3.

## Impact Map

**Touched surface:** none.

---

### Task 1: Foundation (hub — depended on by tasks 2, 3, 4)

**Files:**
- Create: `hub/foundation.txt`

**Steps:**
1. Create foundation file

**Verify:**
Run: `test -f hub/foundation.txt`
Expected: exit 0

### Task 2: Consumer A

**Files:**
- Create: `hub/a.txt`

**Depends on:** Task 1

**Steps:**
1. Create a.txt

**Verify:**
Run: `test -f hub/a.txt`
Expected: exit 0

### Task 3: Consumer B

**Files:**
- Create: `hub/b.txt`

**Depends on:** Task 1

**Steps:**
1. Create b.txt

**Verify:**
Run: `test -f hub/b.txt`
Expected: exit 0

### Task 4: Consumer C

**Files:**
- Create: `hub/c.txt`

**Depends on:** Task 1

**Steps:**
1. Create c.txt

**Verify:**
Run: `test -f hub/c.txt`
Expected: exit 0

### Task 5: Standalone

**Files:**
- Create: `hub/d.txt`

**Steps:**
1. Create d.txt

**Verify:**
Run: `test -f hub/d.txt`
Expected: exit 0
