---
name: characterization-test
description: "Use before refactoring legacy code, or when the user says 'characterization test', 'lock behavior', '特征测试', 'write characterization tests', 'snapshot behavior'. Generates Swift Testing test cases that capture current behavior as a safety net before refactoring."
compatibility: Requires macOS and Xcode
---

# Characterization Test

Lock current behavior with test cases before refactoring. Uses Swift Testing framework (`@Test` + `#expect`).

## When to Use

- Before refactoring existing code
- Before migrating patterns (UIKit → SwiftUI, Combine → async/await)
- When inheriting unfamiliar codebase
- Before replacing a dependency

## Process

### Step 1: Identify Target

Ask user to specify one of:
- **Module/directory**: all public types in that module
- **Specific files**: named files
- **Type name**: a specific struct/class/protocol

If user says "the code I'm about to refactor" without specifics, check recent git changes or ask.

### Step 2: Analyze Interfaces

For each target type, extract:

1. **Public/internal methods**: name, parameters, return type
2. **Computed properties**: name, type
3. **Initializers**: parameter combinations
4. **Observable side effects**:
   - Published properties (`@Published`, `@Observable`)
   - Delegate callbacks
   - Notification posts
   - File/database writes
   - Network requests (identify; mock in tests)
5. **Error paths**: methods that `throw`, optional returns, `Result` types
6. **Edge cases from code inspection**:
   - Boundary values (empty arrays, nil optionals, zero counts)
   - Guard/precondition statements (reveal invalid input handling)

Output analysis:

```
## Interface Analysis: {TypeName}

### Methods ({N})
- `func methodName(param: Type) -> ReturnType` — {one-line behavior description}
  Side effects: {none / publishes to X / writes to Y}

### Properties ({N})
- `var propName: Type` — {computed/stored, observable?}

### Initializers ({N})
- `init(param: Type)` — {what it sets up}

### Error Paths ({N})
- `methodName` throws `ErrorType` when {condition}

### Identified Edge Cases ({N})
- {description of boundary/edge case from code}
```

### Step 3: Generate Test Cases

For each item from Step 2, generate Swift Testing test cases.

**Test file naming**: `{TypeName}CharacterizationTests.swift`

**Test structure**:

```swift
import Testing
@testable import {ModuleName}

// MARK: - {TypeName} Characterization Tests
// Generated: {date}
// Purpose: Lock current behavior before refactoring.
// DELETE these tests after refactoring is verified with proper unit tests.

struct {TypeName}CharacterizationTests {

    // MARK: - Initialization

    @Test("init sets default values")
    func initDefaults() {
        let sut = TypeName()
        #expect(sut.property == expectedValue)
    }

    // MARK: - Method Behavior

    @Test("methodName returns X when given Y")
    func methodNameHappyPath() {
        let sut = TypeName()
        let result = sut.methodName(param: testValue)
        #expect(result == expectedValue)
    }

    @Test("methodName handles empty input")
    func methodNameEmptyInput() {
        let sut = TypeName()
        let result = sut.methodName(param: [])
        #expect(result == expectedEmptyResult)
    }

    // MARK: - Error Paths

    @Test("methodName throws when input is invalid")
    func methodNameThrows() {
        let sut = TypeName()
        #expect(throws: SpecificError.self) {
            try sut.methodName(param: invalidValue)
        }
    }

    // MARK: - Side Effects

    @Test("methodName publishes update")
    func methodNamePublishes() async {
        let sut = TypeName()
        sut.methodName(param: value)
        #expect(sut.publishedProperty == expectedValue)
    }
}
```

**Test generation rules**:
- One `@Test` per observable behavior (not per line of code)
- Test name describes the behavior being locked, not the implementation
- Use `#expect` for assertions, `#require` for preconditions
- For async methods: use `async` test functions
- For types with dependencies: create minimal inline stubs (not full mock framework)
- Mark tests with `// CHARACTERIZATION` comment for easy cleanup later

### Step 4: Run Tests to Establish Baseline

Execute:

```bash
xcodebuild test \
  -scheme {scheme} \
  -destination 'platform=iOS Simulator,name=iPhone 16' \
  -only-testing:{testTarget}/{TypeName}CharacterizationTests \
  -quiet 2>&1
```

If any test fails:
1. Read the failure output
2. **Fix the expected value to match actual behavior** — this is characterization testing; the current behavior IS the expected behavior
3. Re-run until all pass

If build fails (missing imports, wrong module name):
1. Fix compilation errors
2. Re-run

Report baseline:

```
## Baseline Results

- Tests generated: {N}
- Tests passing: {N}
- Tests fixed (expected value adjusted): {N}
- Build issues resolved: {N}
```

### Step 5: Output Summary

```
## Characterization Test Summary

### Coverage
| Type | Methods | Properties | Error Paths | Edge Cases | Total Tests |
|------|---------|------------|-------------|------------|-------------|
| {TypeName} | X | Y | Z | W | N |

### Test Files
- `{TestTarget}/{TypeName}CharacterizationTests.swift`

### Baseline
All {N} tests passing at commit {SHA short}.

### Next Steps
- Proceed with refactoring; run these tests after each change
- When refactoring is complete, replace characterization tests with proper unit tests
- Delete characterization test files when no longer needed
```

## Principles

1. **Lock behavior, don't judge it**: characterization tests capture what IS, not what SHOULD BE. A bug in current code becomes an expected behavior in the test. Fix bugs after refactoring, not during characterization.
2. **Test observable behavior**: test public API and side effects, not private implementation details. Private methods change during refactoring; public contracts should not.
3. **Swift Testing only**: use `@Test` + `#expect` + `#require`. No XCTest.
4. **Minimal mocking**: inline stubs over mock frameworks. Characterization tests should be simple and self-contained.
5. **Disposable by design**: these tests exist to make refactoring safe. They should be deleted and replaced with proper unit tests after refactoring is verified.

## Completion Criteria

- Target types analyzed (Step 2 output produced)
- Test cases generated covering methods, properties, error paths, and edge cases
- All tests passing (baseline established via `xcodebuild test`)
- Summary with coverage table delivered
