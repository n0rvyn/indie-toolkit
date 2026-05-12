# Feedback Loop Ladder

Used by `fix-bug` Step 0.9. Pick the lowest viable level; declare it before Step 1 of the bug investigation.

**This is the skill.** Pocock's diagnose Phase 1 thesis: if you have a fast, deterministic, agent-runnable pass/fail signal for the bug, you will find the cause — bisection, hypothesis-testing, and instrumentation all just consume that signal. If you don't have one, no amount of staring at code will save you. Before generating any falsifiable assertion in Step 3, declare your Feedback Loop level.

**The ladder (try in roughly this order, lowest viable wins):**

1. **Failing test** at whatever seam reaches the bug — unit, integration, or E2E.
2. **Curl / HTTP script** against a running dev server.
3. **CLI invocation** with a fixture input, diffing stdout against a known-good snapshot.
4. **Headless browser script** (Playwright / Puppeteer) — drives UI, asserts on DOM/console/network.
5. **Replay a captured trace.** Save a real network request / payload / event log to disk; replay it through the code path in isolation.
6. **Throwaway harness.** Spin up a minimal subset of the system (one service, mocked deps) that exercises the bug code path with a single function call.
7. **Property / fuzz loop.** If the bug is "sometimes wrong output", run 1000 random inputs and look for the failure mode.
8. **Bisection harness.** If the bug appeared between two known states (commit, dataset, version), automate "boot at state X, check, repeat" so you can `git bisect run` it.
9. **Differential loop.** Run the same input through old-version vs new-version (or two configs) and diff outputs.
10. **HITL bash script.** Last resort. If a human must click, drive *them* with a structured loop so the loop is still mechanized; captured output feeds back to you.

**Required output before proceeding to Step 1:**

```
[Feedback Loop] level={N} (1–10) — {one-line description of the signal}
Command: {exact command to invoke the loop}
Pass: {what stdout / exit code / state means "bug NOT present"}
Fail: {what stdout / exit code / state means "bug PRESENT"}
```

If you cannot reach any level (no test infra, no curl-able endpoint, no fixture), that is the first thing to fix — not the bug. State `[Feedback Loop] level=0 — not constructable, blocking on: {what's missing}` and either build it or escalate to the user.

**Step 3 cross-reference:** each assertion in Step 3 must declare which Feedback Loop level its `Verify:` line runs on. Verifying an assertion through a different channel than declared here is a category error.
