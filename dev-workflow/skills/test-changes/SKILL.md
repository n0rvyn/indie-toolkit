---
name: test-changes
description: "Use when the user says 'test changes', 'run tests', 'test the build', or after execute-plan completes in a run-phase. Runs the project's build/test/lint suite and returns a filtered report with errors only. Branches on project type: Apple projects (.xcodeproj/.xcworkspace) run xcodebuild from the main session with diff-scoped -only-testing; other projects dispatch the dev-workflow:test-runner sub-agent."
---

## Overview

Two execution paths:

- **Apple path** (project root contains `.xcodeproj` or `.xcworkspace`): run `xcodebuild test` from the **main session**, scoped to suites in the recent diff, with simulator pre-flight + crash recovery. **Do NOT dispatch a sub-agent.**
- **Other projects**: dispatch the `dev-workflow:test-runner` sub-agent.

In both cases, write a structured report to `.claude/test-reports/test-run-{ts}.md` so `run-phase` parsing stays consistent.

### Why "main session only" for Apple

The real constraint is **single-process serialization** of `xcodebuild test`, not anything Apple-specific about which process invokes it. Two concurrent `xcodebuild test` runs break in three ways:

1. **DerivedData `build.db` SQLite lock**: both processes write to the same `~/Library/Developer/Xcode/DerivedData/<Project>-<hash>/Build/Intermediates.noindex/XCBuildData/build.db`, second writer fails with `database is locked`.
2. **`simctl` state is global**: one process can shut down the simulator the other is using, mid-test.
3. **CoreSimulator daemon contention**: under multi-sim CPU load, the simulator's internal system apps (SpringBoard, MobileCal) can't finish launching within 30 seconds → FRONTBOARD process-launch watchdog SIGKILLs them → entire test run aborts.

The main session is single-threaded, so running `xcodebuild test` from there naturally serializes. Sub-agents could *in principle* run tests too — but the agent framework can dispatch sub-agents in parallel, and there's no mutex primitive across them. So the simplest enforceable rule is "main session only". This is an execution-discipline choice, not an Apple platform rule.

## Process

### Step 1: Detect Project Type

From project root, check for Apple project markers:

```bash
if ls *.xcodeproj *.xcworkspace 2>/dev/null | head -1 > /dev/null; then
  echo "apple"
else
  echo "other"
fi
```

If `apple` → **Step 2A**. Otherwise → **Step 2B**.

### Step 2A: Apple Path (run from main session)

Run all `xcodebuild` commands directly via Bash from the main session. Never delegate to a sub-agent.

#### A1. Identify scheme

```bash
SCHEME=$(xcodebuild -list -json 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    schemes = (d.get('project') or d.get('workspace') or {}).get('schemes', [])
    print(schemes[0] if schemes else '')
except Exception:
    pass
")

if [[ -z "$SCHEME" ]]; then
  echo "❌ No scheme detected. Configure a shared scheme in Xcode (Product → Scheme → Manage Schemes → check 'Shared')."
  # Write minimal FAIL report at A8 and return.
fi
```

The python block tolerates malformed JSON, missing `project`/`workspace` keys, and empty `schemes` arrays — all return empty `$SCHEME` instead of a traceback.

#### A2. Derive `-only-testing` filters from diff

```bash
# Prefer uncommitted changes; if empty, fall back to the most recent commit.
CHANGED=$(git diff --name-only HEAD 2>/dev/null)
[[ -z "$CHANGED" ]] && CHANGED=$(git diff --name-only HEAD~1..HEAD 2>/dev/null)

# Filter to Swift test files: under any *Tests/ directory (root- or nested-), file ending in Tests.swift.
# Matches: LifuelTests/RecordHistoryRowTests.swift (root), LifuelTests/Sub/TimerStateTests.swift (nested),
#          apps/X/MyAppTests/AuthTests.swift (deep). Drops non-test files like LifuelTests/Helper.swift.
TEST_FILES=$(echo "$CHANGED" | grep -E '(^|/)[^/]*Tests/.*Tests\.swift$' || true)
```

For each test file, derive `-only-testing:<TestTarget>/<SuiteName>`:

- **TestTarget**: walk *up* the path from the file; the deepest ancestor directory whose name ends in `Tests` is the target (handles `apps/Tests/MyAppTests/Foo.swift` → `MyAppTests`, not `Tests`).
- **SuiteName**: file basename without `.swift` (e.g., `RecordHistoryRowTests`).

```bash
ONLY_TESTING_FLAGS=""
# Use `while read` instead of `for f in` — paths with spaces (legal in Xcode group folders) word-split otherwise.
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  # Walk up the path, find the deepest ancestor matching *Tests.
  TARGET=""
  d=$(dirname "$f")
  while [[ "$d" != "." && "$d" != "/" && -n "$d" ]]; do
    base=$(basename "$d")
    if [[ "$base" == *Tests ]]; then
      TARGET="$base"
      break
    fi
    d=$(dirname "$d")
  done
  [[ -z "$TARGET" ]] && continue
  SUITE=$(basename "$f" .swift)
  ONLY_TESTING_FLAGS+=" -only-testing:${TARGET}/${SUITE}"
done <<< "$TEST_FILES"
```

**Fallback policy**: if `ONLY_TESTING_FLAGS` is empty, do **NOT** run the full test suite — full-suite runs are 5–15 minutes on real projects and waste CI time when the diff doesn't touch any test files. Instead, run **build only** in A4 and report:

> `No *Tests.swift files in diff — ran build only. Re-invoke with explicit -only-testing targets to run tests.`

#### A3. Simulator pre-flight

```bash
BOOTED=$(xcrun simctl list devices booted | grep -oE '[A-F0-9-]{36}')
COUNT=$(echo "$BOOTED" | grep -c .)

if [[ "$COUNT" -gt 1 ]]; then
  xcrun simctl shutdown all
  sleep 3
  xcrun simctl boot "iPhone 16 Pro"
  sleep 8
elif [[ "$COUNT" -eq 0 ]]; then
  xcrun simctl boot "iPhone 16 Pro"
  sleep 8
fi

BOOTED_UDID=$(xcrun simctl list devices booted | grep -oE '[A-F0-9-]{36}' | head -1)
[[ -z "$BOOTED_UDID" ]] && { echo "❌ Could not boot simulator"; exit 1; }

# Capture the actual device name for the report (the booted sim may not be iPhone 16 Pro
# if the user already had a different sim running before this skill ran).
DEVICE_NAME=$(xcrun simctl list devices | grep "$BOOTED_UDID" | head -1 | sed -E 's/^[[:space:]]+//; s/ \([A-F0-9-]+\).*$//')
```

Note: `xcodebuild test` shuts down the destination sim on completion (§9), so on the next invocation `COUNT == 0` is normal — auto-boot recovers.

#### A4. Build (always run)

```bash
xcodebuild build \
  -scheme "$SCHEME" \
  -destination "platform=iOS Simulator,id=$BOOTED_UDID" \
  -quiet 2>&1 | tee /tmp/test-changes-build.log
BUILD_EXIT=${PIPESTATUS[0]}
```

If `BUILD_EXIT != 0`: write report with build failure, skip A5, return.

#### A5. Test (only if `ONLY_TESTING_FLAGS` non-empty)

```bash
RESULT_BUNDLE="/tmp/test-run-$$.xcresult"
LOG="/tmp/test-changes-test.log"

xcodebuild test \
  -scheme "$SCHEME" \
  -destination "platform=iOS Simulator,id=$BOOTED_UDID" \
  $ONLY_TESTING_FLAGS \
  -resultBundlePath "$RESULT_BUNDLE" \
  2>&1 | tee "$LOG"
TEST_EXIT=${PIPESTATUS[0]}
```

#### A6. Recovery + retry-once

After a non-zero exit, **grep the log for crash/hang tokens** (these can pair with various exit codes; plain assertion failures must NOT trigger recovery):

```bash
NEEDS_RECOVERY=0
TRIGGER_TOKEN=""
if [[ "$TEST_EXIT" -ne 0 ]]; then
  TRIGGER_TOKEN=$(grep -oE '0x8BADF00D|IDELaunchiPhoneSimulatorLauncher|FRONTBOARD|RequestDenied|process-launch watchdog' "$LOG" | head -1)
  [[ -n "$TRIGGER_TOKEN" ]] && NEEDS_RECOVERY=1
fi

if [[ "$NEEDS_RECOVERY" -eq 1 ]]; then
  xcrun simctl shutdown all
  killall -9 com.apple.CoreSimulator.CoreSimulatorService 2>/dev/null
  sleep 5
  xcrun simctl boot "iPhone 16 Pro"
  sleep 8
  BOOTED_UDID=$(xcrun simctl list devices booted | grep -oE '[A-F0-9-]{36}' | head -1)
  DEVICE_NAME=$(xcrun simctl list devices | grep "$BOOTED_UDID" | head -1 | sed -E 's/^[[:space:]]+//; s/ \([A-F0-9-]+\).*$//')

  # Retry once with same flags. Use a separate log so A8 can include both runs if needed.
  RETRY_LOG="/tmp/test-changes-test-retry.log"
  xcodebuild test \
    -scheme "$SCHEME" \
    -destination "platform=iOS Simulator,id=$BOOTED_UDID" \
    $ONLY_TESTING_FLAGS \
    -resultBundlePath "${RESULT_BUNDLE}-retry" \
    2>&1 | tee "$RETRY_LOG"
  TEST_EXIT=${PIPESTATUS[0]}
  LOG="$RETRY_LOG"   # subsequent filter (A7) operates on the retry's output
fi
```

If recovery retry also fails with the same tokens: report `FAIL — simulator unrecoverable, manual intervention required`. Do not retry a second time.

#### A7. Filter output

Keep only these line patterns in the report. Build phase reads `/tmp/test-changes-build.log`; test phase reads `$LOG` (which A6 reassigns to the retry log if recovery ran, so the filter sees the most recent test output):

- Compile errors/warnings: `error:`, `warning:`
- XCTest: `Test Case '-[…]' passed|failed`
- Swift Testing: lines starting with `✓ ` or `✗ `, plus `◇ Test run`
- Suite summary: `Test Suite '…' passed|failed`, `Executed N tests, with M failures`
- Crash tokens: `0x8BADF00D`, `FRONTBOARD`, `RequestDenied`

Drop everything else (compile noise, Copying / Linking lines, etc.). Cap each section at 200 lines; append `... (N more lines truncated)` if exceeded.

#### A8. Write report

Create `.claude/test-reports/` if missing. Write `.claude/test-reports/test-run-{YYYY-MM-DDTHH-MM-SS}.md`:

```markdown
## Test Report

**Timestamp:** {ISO 8601}
**Project:** {root basename}
**Path:** apple
**Scheme:** {SCHEME}
**Simulator:** {DEVICE_NAME} ({BOOTED_UDID})
**Status:** {PASS | FAIL}

### Build
**Command:** `xcodebuild build -scheme {SCHEME} -destination "...,id={UDID}"`
**Result:** {PASS | FAIL} (exit code {N})
{filtered build output if FAIL}

### Tests
**Command:** `xcodebuild test -scheme {SCHEME} -destination "...,id={UDID}" {ONLY_TESTING_FLAGS}`
**Targets:** {list of -only-testing flags, or "skipped — no test files in diff"}
**Result:** {PASS | FAIL | SKIPPED} (exit code {N})
**Recovery:** {none | applied — {token that triggered}}
{filtered per-test pass/fail lines if FAIL}

### Lint
**Result:** SKIPPED (no lint configured for Apple projects)
```

#### A9. Plan-supplied commands — ignored on Apple path

The `test-runner` agent (non-Apple) extracts verification commands from the plan file. The Apple path **ignores** plan-supplied commands to keep all `xcodebuild test` invocations on the established invocation template (`id=$BOOTED_UDID` + `-only-testing` + isolated `-resultBundlePath`). A plan-supplied command using `name=` instead of `id=`, or omitting `-only-testing`, would re-introduce the failure modes Step 2A is designed to prevent. If the plan needs different test targets, surface that in the report and let the user decide.

### Step 2B: Other Projects (dispatch sub-agent)

For non-Apple projects, dispatch `dev-workflow:test-runner` as before:

```
Run the project's build, test, and lint suite.

Project root: {project root}
Plan file: {plan file path, or "none" if standalone}
```

The agent detects the project type (Node / Swift Package / Cargo / Go / Python) and writes a report to `.claude/test-reports/`.

### Step 3: Process Results

1. Read the report file (Apple path: written in A8; sub-agent path: from agent's return).
   - If sub-agent didn't return a path, search `.claude/test-reports/test-run-*.md` and use the most recent.
2. Present summary to user:
   - Build: PASS/FAIL
   - Tests: X/Y passed (Z failed) — for Apple path, also note `Recovery: applied` if it ran
   - Lint: PASS/FAIL/SKIPPED
3. If any failures: show the filtered errors from the report (already filtered — do not re-filter).

**Standalone mode** (not within run-phase):
- All pass: "All build, test, and lint checks pass."
- All pass + 改动 > 0：追加 hint「下一步可 `/review-execution` 做 4-lens 深审（correctness / test-coverage / breaking-changes / root-cause-depth）」
- Failures: present errors and suggest fixing in main context.

## State Integration

When running within a phase orchestrated by `run-phase`:

- After report is written, do NOT update `phase_step` (orchestrator owns state transitions)
- Output the report path for run-phase to read
- Output: "Test run complete. Returning to run-phase."

## Completion Criteria

- Project type detected (apple / other)
- Apple path: build + (test or skip-with-reason) executed from main session, recovery applied at most once if triggered, report written
- Other path: test-runner agent dispatched and returned, report read
- Summary presented to user
- When in run-phase context: report path output for orchestrator
