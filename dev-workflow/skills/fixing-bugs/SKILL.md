---
name: fixing-bugs
description: "Use when the user reports an error with stack trace or screenshot, describes unexpected behavior, or build/test failures occur. Systematically diagnoses through reproduction, hypothesis, value domain tracing, and parallel path detection."
---

## Input

Trigger this command when:
- User reports an error with stack trace or screenshot
- User describes unexpected behavior
- Build/test failures occur

If input is incomplete, ask for:
1. Steps to reproduce
2. Expected vs actual behavior
3. Full error message or stack trace

## Process

1. **Reproduce first**
   - Confirm the bug can be reproduced
   - If cannot reproduce: ask for more context, do not guess
   - Document the exact steps that trigger the bug

2. **Understand the error**
   - Read the complete error message and stack trace
   - Identify the exact location where the error occurs
   - Note any relevant context (user action, data state)

3. **Form hypothesis**
   - Based on error type, make an educated guess
   - Common categories: constraint conflict, nil value, boundary condition, race condition, state inconsistency

4. **Verify hypothesis**
   - Find evidence to support or refute the hypothesis
   - Read relevant code to understand the flow
   - If hypothesis is wrong, form a new one based on findings

5. **Trace value domain** (trigger: bug symptom is an incorrect value in display/log/data transfer)
   - Reverse-trace from bug location to data source (record each variable rename)
   - Forward-Grep all consumers from source (using source field name + every intermediate variable name)
   - Verify unit/domain/format assumptions at each consumer
   - Output format:
     ```
     [值域检查] {file:line} — {生产/消费} — 假设值域 {X} — ✅ 一致 / ❌ 同类问题
     ```
   - All ❌ must be fixed in the same pass
   - Skipping this step for value-related fixes = incomplete fix, even if original symptom disappears

6. **Check for parallel paths** (trigger: Step 5 finds multiple producers, or same core function has multiple upstream callers)
   - List all processing paths from source to sink
   - Check coordination mechanisms between paths (shared state, mutex, idempotency check)
   - Format:
     ```
     [路径检查] {核心函数}
     - 路径 A: {file:line} → {file:line} → {核心函数}
     - 路径 B: {file:line} → {核心函数}
     - 协调机制: {具体代码位置 / 无}
     ```
   - Parallel paths without coordination = architectural issue; flag as "⚠️ needs architectural fix" and inform user; do not fix only one path

7. **Fix the root cause**
   - Address the actual cause, not just the symptom
   - Consider edge cases and related scenarios
   - Ensure the fix doesn't introduce new issues

8. **Verify the fix**
   - Build the project
   - Reproduce the original bug scenario - confirm it's fixed
   - Test related scenarios to catch regressions
