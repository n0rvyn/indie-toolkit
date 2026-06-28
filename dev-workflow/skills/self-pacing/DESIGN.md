# self-pacing — design invariants (maintainer note)

Not loaded at runtime. Read this before changing the stop / handoff / resume behavior. Each invariant looks removable until you trace why it exists; the three are interlocked — removing or "enhancing" one breaks the resume model.

## 1. A STOP is a complete handoff the instant it fires

At every STOP the skill writes the thin card (`<slug>-handoff.md`) and **ends the turn**. The run is now fully on disk, nothing pending. Resume is **session-independent**:

- **Hot** — same session: the prompt cache keeps the conversation prefix warm, so a reply within the cache TTL resumes cheaply with nothing held. On a 1-hour-cache setup that covers ~an hour of away-time for free.
- **Cold** — a brand-new session just reads the card + follows its Pointers.

Nothing depends on the original session staying alive. That is the whole point of AFK durability.

## 2. Run log ≠ handoff card — it does NOT hand off per task or per batch

| | written when | ends the turn? |
|---|---|---|
| Run log (`<slug>.md`) | incrementally, on **every** auto-action (crash-safe record) | no |
| Handoff card (`<slug>-handoff.md`) | **only at a STOP** | yes |

Between stops the skill runs continuously, suppressing pacing pauses. It cards-out only at a **severity** gate (blocking decision / severe failure / explicit `<!-- checkpoint -->`; + phase seam in phase mode) — **never** at a clean batch/segment boundary.

> "跑一批就 handoff" is wrong. "severity 停才 handoff,每步只记 log" is right.

## 3. No timer, no scheduling, no auto-resume — do not add one

The recurring tempting enhancement is "notify, wait N minutes, then auto-handoff if no reply." It is wrong on three counts:

- **(a) Nothing to schedule.** The handoff already completed at stop-time (invariant 1). There is no future action to fire.
- **(b) A timer breaks durability.** ScheduleWakeup / cron only fire inside a *live* session. Using one re-couples resume to a session staying alive — directly breaking the session-independence of invariant 1. AFK means the session may be dead; the on-disk card must work regardless.
- **(c) Holding the session IS the pile-up.** Keeping the session open for the timed window is exactly the pile-up the immediate end-turn exists to eliminate.

The warm "did you reply in time?" window a timer would buy is already provided **for free** by the prompt cache (invariant 1): within the cache TTL any reply resumes hot with no held session; beyond it, the card gives a cheap cold resume. Both paths are covered without a timer.

This is why "No timer, no background scheduling" is a Hard Rule in SKILL.md — it is a consequence of the architecture, not a tunable.

## Rejected enhancement ideas (and why)

Evaluated and rejected as over-design relative to the AFK user's intent (`/self-pacing` already implies: verified plan exists, long run expected, don't interrupt unless truly blocked):

- **Token budget / runaway cap** — contradicts "I expect a long run." AFK = long by intent.
- **Scope-drift check at phase seams** — relies on the user editing the dev-guide mid-run, which they don't after authorizing and walking away.
- **Read-only diagnosis on failure cards** — the skill deliberately makes diagnosis the user's; auto-diagnosis AFK risks confident-wrong.
- **Bounded transient-failure retry** — "no blind retry" is deliberate; masks real failures.
- **Wait-then-auto-handoff timer** — see invariant 3.
