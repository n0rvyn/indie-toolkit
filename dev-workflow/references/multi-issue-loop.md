# Multi-Issue Loop (reference)

Used by `fix-bug` when input is a backlog of issues that share a verification surface — the running system itself (HTTP API, CLI, REPL, chat interface, mobile deeplink) is what proves each fix landed.

Single-bug flow stays inside the main `fix-bug` skill. This reference governs the orchestration when **N issues** must be fixed against a system that talks back.

## When this loop applies

Enter this loop only when **all** of these hold:

1. The input is 2+ issues/bugs (typically referenced as `#N1 #N2 ...`, or "fix these N issues", or "dogfood this batch")
2. The system under repair exposes an end-to-end verification surface — at least one of: REST/RPC API, CLI command, chat agent, mobile app deeplink, REPL
3. The user expects fixes to be verified through that surface (not just unit-test green)

If any of these is missing, fall back to single-bug `fix-bug` per issue.

## Why verify-then-fix order matters

Most fix flows write the patch, then ask "did it work?" That order makes acceptance criteria implicit and easy to fudge — green tests aren't proof the bug is gone if the test never measured the bug.

This loop inverts the order: **define the surface-level reproducer and the user-perspective check before touching code**. Then the verify step is mechanical replay, not interpretation.

## Hard rules

1. **Baseline first**. Before any fix, reproduce the current failure through the verification surface and freeze the evidence (request id, exact error string, log excerpt). If you cannot reproduce, the reported bug is suspect — do not write a fix against a guess.

2. **Verify boundary ≠ issue boundary**. Group issues into the smallest set whose joint fix makes the surface-level reproducer go green. One issue per bundle is fine; multiple issues per bundle is fine. Splitting issues that can only pass together yields false-negative verify and wasted cycles.

3. **Verification surface is the acceptance contract**. Every bundle has a reproducer driven through the surface (`curl`/`gh`/`xcrun simctl openurl`/CLI invocation) **plus** a user-perspective check (the phrasing or action a real user would use). If the surface can't drive the reproducer (no endpoint, no flag, no dry-run mode), that is itself a gap in the system — file it, fix it before the bundle.

4. **Real runtime, no mocks at the verify boundary**. `test-changes` (unit + e2e with mocks) is necessary but not sufficient. The bundle is not done until the running system passes the reproducer.

5. **Restart / reload safety**. Before triggering a rebuild + restart of the verification surface, confirm no in-flight work that would be killed (running jobs, live user sessions, open transactions). Announce a maintenance window if a human is at the keyboard.

6. **Regression replay accumulates**. Bundle N's verify run includes Bundle 1..N-1's reproducers. The reproducer files become the regression suite, mechanically.

7. **Failure routes are typed**.
   - `test-changes` fails → back to plan-execute loop. Do **not** advance to the surface verify.
   - End-to-end verify fails but tests pass → **postmortem first**: was acceptance criteria wrong (back to bundle definition) or implementation wrong (back to plan)? Do not blind-retry.

8. **Side-effect isolation**. If the verification surface touches real channels (email/IM/webhook/push notification/payment), before running verifies swap delivery targets to test-only channels or enable dry-run. Restore after.

## Process

### Step L0 — Surface the issue list

Receive the list of bugs to fix. Confirm with the user. For each, ensure there is (or will be) a GitHub issue with:
- Symptom (one sentence)
- Reproducer pointer (cron name, API call, chat phrase, CLI command, deeplink)
- Prior hypotheses (`### Prior Hypotheses` block — file them so a later `fix-bug #N` read picks them up)

If issues are missing, file them now via `gh issue create` before continuing.

### Step L1 — Baseline reproduction

For each issue, drive the failure through the verification surface of the real runtime. Save:
- The exact request (curl with explicit headers / CLI invocation with explicit args / chat phrase verbatim)
- The exact response (jq-extracted error / exit code / contract violation message / observed bad UI state)
- One representative log excerpt (truncated to relevant tool calls / function frames)

Write the baseline evidence to `.claude/multi-issue-loop/baseline/<issue-id>.md` so it is durable across context resets.

**Stop condition**: if the baseline cannot be captured (surface doesn't expose the failure), the surface itself has a gap. Open a tracking issue and patch the surface first — that becomes Bundle 0.

### Step L1.5 — Disambiguate competing hypotheses

If any issue rests on a hypothesis that could be discharged by a cheap discriminating test, run it **before** bundling. Common patterns:

- "Tool X is unavailable because of config Y" → check a known-successful path that should also have triggered the bug; if that path succeeded, the hypothesis is wrong
- "Path A behaves differently from path B" → diff the entry points; if they converge on a shared function, treat them as one path
- "Feature F is broken" → confirm F is actually exercised by the failing scenario (not just present in the codebase)

Capture the discriminating evidence to `.claude/multi-issue-loop/disambig/<issue-id>.md`. Issues whose hypothesis fails this check are demoted to "phantom" and dropped from the bundle list. Document the demotion so the same hypothesis doesn't resurface in a later cycle.

**Why this exists**: Step L2 (bundling) implicitly assumes diagnoses are settled. Skipping disambiguation replaces the workflow's "false-negative verify" failure mode with a new one: bundles that pass verify because the unverified hypothesis was wrong-but-harmless, leaving the real cause in place.

### Step L2 — Bundle grouping + dependency graph

Build the dependency graph: issue B depends on issue A if A's fix changes B's reproducer or acceptance criteria. Group issues such that **each bundle is end-to-end verifiable on its own**.

Output: `.claude/multi-issue-loop/bundles.md`

```markdown
## Bundle A: <one-line outcome>
- Issues: #N1, #N2
- Joint reproducer: <exact surface-level call + user-perspective phrasing>
- Acceptance: <observable check, must be derivable from surface response>
- Depends on: (none | Bundle X)
```

Single-issue bundles are fine. Two-issue bundles need the joint reproducer in writing — if you can't write it, the issues belong in different bundles.

### Step L3 — Isolate side effects

Before the bundle runs through verify:
- Swap delivery rules / template targets to test-only channels
- Snapshot the rows/files you're about to touch (so you can diff after)
- Note any scheduled jobs whose window you're inside — if one fires mid-verify, the run gets contaminated

Restore after the bundle's final verify, not after each attempt.

### Step L4 — Bundle pipeline (per bundle)

For each bundle in dependency order:

**Per-step routing for loop mode** — when this loop invokes `fix-bug`, not every step from fix-bug's linear flow runs at the same scope. Use this table to decide what runs once per bundle vs once per issue:

| fix-bug step | Loop-mode scope | Rationale |
|--------------|-----------------|-----------|
| 0 (parse input + read GitHub issue) | Once per issue (already itemized in L0) | Each issue has its own number/body |
| 0.5 (kb retrieval) | Once per **bundle** at L1 entry | Re-running kb per issue is redundant when issues share keywords |
| 0.7 (project health) | Once per bundle at L1 entry | Health state doesn't change between issues in the same bundle |
| 0.8 (AI-CONTEXT + ubiquitous-language) | Once per bundle at L1 entry | Project context is shared across issues |
| 0.9 (Feedback Loop ladder declaration) | Per issue (declared at L4.0 per-issue diagnostic entry) | Each issue may need a different feedback loop level |
| 1, 2, 2.5, 3, 4, 4.5, 5, 6 | Per issue at L4.0 | These are the diagnostic steps that vary per issue |
| 7 (Plan the fix) | Once per bundle at L4.1 | The plan covers all issues in the bundle |
| 8 (Fix the root cause) | Once per bundle (via L4.3 execute-plan) | Execution covers the whole bundle |
| 9 (Verify the fix) | Once per bundle at L4.6 | The bundle reproducer IS the verify |
| 10 (Tradeoff Report) | Once per bundle at L4.9 | One commit, one tradeoff report |

**L4.0 Diagnostic (route through fix-bug Steps 1-6 per issue)** — for each issue in the bundle, run `fix-bug` Step 0.9 (Feedback Loop declaration) → 1 (Reproduce) → 2 (Understand error) → 2.5 (Understand intent) → 3 (BV assertions) → 4 (Verify assertions) → 5 (Value domain trace) → 6 (Parallel paths). Stop at Step 6; do **not** invoke `fix-bug` Step 7 (`/write-plan`) per-issue — the plan covers the whole bundle and is written in L4.1 below. Skip Steps 0.5/0.7/0.8 (already ran once at L1 bundle entry). Collect the confirmed assertions, value-domain table, and parallel-path findings as input for L4.1.

**L4.1 `/write-plan`** — write the implementation plan covering all issues in the bundle. The plan's verification commands must include the bundle reproducer from L2. The plan's Impact Map must incorporate the value-domain consumers and parallel paths found in L4.0.

**L4.2 `/verify-plan`** — verify the plan. If the plan can pass without satisfying the bundle reproducer, the plan is wrong, not the reproducer — rewrite the plan.

**L4.3 `/execute-plan`** — execute mechanically.

**L4.4 `/test-changes`** — unit + e2e. **Hard gate**: if this fails, return to L4.1. Do not proceed to L4.5.

**L4.5 Rebuild + readiness probe**
- Check no in-flight work that the restart would kill (project-specific check: `curl /tasks?status=running`, `gh run list --status in_progress`, simulator app state, etc.)
- Check no live user sessions on the surface (project-specific: `curl /sessions?status=active`, attached debugger, etc.)
- Announce window if human present
- Run the project's rebuild + restart command (e.g., `pnpm build && pm2 restart app`, `swift build && ./run.sh`, Xcode run in simulator)
- Confirm liveness via readiness probe: `curl /healthz` → ok, `curl /readyz` → ready, or equivalent (CLI: re-run a known-good command; mobile: app launches without crash)

**L4.6 End-to-end verify (the bundle reproducer)**
- Run the surface-level reproducer
- Drive the user-perspective check (real user phrasing/action, exact paste)
- Assert against the acceptance defined in L2

**L4.7 Regression replay**: re-run every prior bundle's reproducer. If any prior bundle regresses, the current bundle's fix has collateral — back to L4.1.

**L4.8 Failure routing** (if L4.6 fails):
- Capture failure evidence to `.claude/multi-issue-loop/failures/bundle-<X>-attempt-<N>.md`
- 5-minute postmortem with one question: **"Did acceptance criteria miss the actual user-visible behavior, or did the implementation miss the criteria?"**
  - Criteria miss → back to L2 (rewrite bundle definition)
  - Implementation miss → back to L4.1 (rewrite plan)
- Blind retry without postmortem is forbidden.

**L4.9 On pass**: commit via conventional-commits (`fix(scope): <bundle outcome>`), close issues with `gh issue close #N --comment "<verify evidence link>"`, link to the evidence file. Move to next bundle.

### Step L5 — Restore side-effect targets

After all bundles pass:
- Restore delivery targets to production channels
- Final regression replay against all bundles
- Capture final state: `.claude/multi-issue-loop/final-state.md`

## State file

Location: `.claude/multi-issue-loop/state.json`

```json
{
  "issues": ["#N1", "#N2", "#N3", "#N4"],
  "bundles": [
    {"id": "A", "issues": ["#N1", "#N2"], "status": "verifying", "reproducer": "path/to/script.sh", "attempt": 1},
    {"id": "B", "issues": ["#N3", "#N4"], "status": "pending"}
  ],
  "current_bundle": "A",
  "current_step": "L4.6",
  "_step_legend": "L0|L1|L1.5|L2|L3|L4.0|L4.1|L4.2|L4.3|L4.4|L4.5|L4.6|L4.7|L4.8|L5",
  "regression_pass_history": [],
  "last_updated": "YYYY-MM-DDTHH:MM:SS"
}
```

Write before starting each step so crash-resume works.

## Anti-patterns this loop exists to prevent

- **Issue-by-issue verify with hidden coupling**: fixing N1, verify "passes" because N2 wasn't exercised, ship, then prod fails on the realistic path
- **Mocked tests as proof**: `test-changes` green, no real-surface replay, regression appears two weeks later
- **Blind retry on verify fail**: same wrong plan executed twice, looks like flake, real cause is acceptance-criteria gap
- **Real-channel pollution**: verifying a daily-email pipeline sends 6 real emails per attempt
- **State drift across bundles**: Bundle C breaks Bundle A's invariant, no one notices because A's reproducer was never re-run
- **Skipping diagnostic**: jumping straight to `/write-plan` per bundle without running `fix-bug` Steps 1-6, leaving root cause unverified

## Outputs

After all bundles pass:
- Closed issues with verify-evidence links
- `.claude/multi-issue-loop/` directory containing baselines, bundle definitions, failure postmortems, final state
- Regression-suite scripts that can be re-run later (`bundles/<X>/reproducer.sh`)
- Conventional-commit history matching bundles 1:1
