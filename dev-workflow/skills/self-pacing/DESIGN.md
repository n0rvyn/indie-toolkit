# self-pacing — design invariants (maintainer note)

Not loaded at runtime. Read this before changing the stop / handoff / resume behavior. Each invariant looks removable until you trace why it exists; the first three are interlocked — removing or "enhancing" one breaks the resume model. Invariant 4 is the opposite hazard: it exists because the stop policy drifts toward stopping if nobody defends the continue side.

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

## 4. Revising a plan is not auto-fixing — and stopping is enumerated, not judged

Two halves of one invariant. Both defend the *continue* side of the policy, which has no natural constituency: an unnecessary stop always looks defensible after the fact, so the table drifts toward stopping unless this is written down.

**(a) `must-revise` is not a severe failure.** The `no-auto-fix` rule (invariant-adjacent, Hard Rules) is grounded in two facts: AFK repo mutation is an unauthorized change, and AFK auto-diagnosis is confidently wrong. Trace them against plan revision and neither holds:

| no-auto-fix's premise | holds for source code | holds for a plan file |
|---|---|---|
| changing it alters product behavior | yes | no — it is text in `docs/06-plans/` |
| the loop is unbounded / no defined exit | yes (a failing test can be "fixed" forever) | no — verify-plan Step 3 caps it at 2 cycles with a defined exit |
| resolving it needs the user's judgment | often | the items that do surface as `blocking` DPs, which stop on their own row |

Classifying `must-revise` as severe produced the observed failure: a guide-mode run that writes its own phase plan at Step 3.1 halts on its first verification round, handing off before one line of code exists. The plan-authoring inner loop was mistaken for a run failure. If you are about to "restore" `must-revise` to the severe row, you are re-introducing that.

**(b) There is no default stop.** The terminal conditions are a closed enumeration (the Stop Policy rows, or green). Do **not** add a judged terminal like "the best state reachable in this session", "good enough to hand off", or a quality bar the model scores itself against. Such a criterion is unfalsifiable and always satisfiable — every premature stop can be narrated as the best attainable state — so it degrades into "stop whenever it feels hard". `Conservative default` (ambiguous → blocking) is deliberately scoped to *severity classification of something that already happened*; it is not a bias toward stopping, and widening it to cover "should I keep working" reproduces (b).

**The observed instance of (b): context occupancy.** On 2026-08-07 a run was about to start and the driver instead recommended moving all six remaining phases to a new session, on the stated ground that 「这轮上下文已经很满」. Measured occupancy at that message was **283,947 of 1,000,000 tokens — 28%**; two earlier instances measured 57% and 73%. The mechanism is worth naming because it is not laziness: the model has no token counter, so it substitutes a felt proxy ("this session has been long, there have been many tool outputs"), and that proxy is uncorrelated with the real number. This skill's own architecture then makes the wrong move look free — invariant 1 advertises session-independent resume, so "start it in a fresh session" reads as *using* the design rather than evading the work. It is still (b): an unfalsifiable self-assessment used as a terminal. SKILL.md Hard Rules names it explicitly, in environment-neutral terms — the skill ships to installs that have no measurement wired up, so it may require *a* measured figure without presuming *which* mechanism supplies it.

**Closing it mechanically (owner's environment, not a plugin dependency).** Hooks do not receive `context_window`; only the status line does. So the owner's setup mirrors the harness's own numbers from `~/.claude/statusline.py` to `~/.claude/.ctx-cache/<session_id>.json`, and a `UserPromptSubmit` hook (`~/.claude/hooks/context-budget.py`) injects them each turn as a `[ctx]` line, with a policy floor of 80% below which proposing `/clear`, a new session, a handoff, or a scope cut is forbidden. The two user-wide rules that consume it are CLAUDE.md 行为约束 →「上下文余量不授权收尾」 (triggers on the number, so motive is not an exit) and 禁止行为 →「断言上下文余量而不引 `[ctx]` 实测数」. None of this is required by the skill; it is one worked example of the environment obligation SKILL.md states abstractly.

**(c) This invariant is inherited, not invented.** Do not read (a)/(b) as filling a gap in the user-wide CLAUDE.md. That file already governs stopping directly, in two rules that both outrank a skill file:

- 行为约束 →「资源不授权跳步」:「…不是跳过流程步骤、**中断执行**、或建议"先保存进度"的理由…禁止以上下文消耗为由主动暂停或拆分正在进行的任务」
- 禁止行为 →「把还在跑的验证写成「未完成 / 待办 / 下轮再看」交回用户」:「先把它**跑到出结论（通过 / 失败 / 一个具体的阻塞点）**…真阻塞才允许写，并写清阻塞在哪一步、解除条件是什么」

The second is already the exact shape of this invariant: terminate on an enumerated outcome — pass / fail / **one concrete blocking point** — and when you do hand back, state where it blocked and what unblocks it, which is precisely the handoff card's `Why` + `Next action`. By CLAUDE.md's own conflict order (禁止行为 > 行为约束 > … > 计划细节), it already outranks this skill's Stop Policy; a premature stop was a rule violation before this file existed.

What was missing was never a rule. It was this skill's **explicit inheritance** of one: the Stop Policy table restated severity in local terms and, in restating it, silently dropped the continue side — so a run reading only SKILL.md saw `When in doubt, stop` with nothing opposing it. The three-gate check in SKILL.md is the local instrument for the same constraint (its interactive twin, CLAUDE.md 行为约束 →「重大决策提问前的三关自检」, governs *asking*; AFK the same threshold has to be applied to *stopping*, because the user is not there to answer either way). Keep both anchored to the CLAUDE.md rules above; if they are ever reworded upstream, reword here too rather than letting this file drift into a competing local doctrine.

## 5. Two bounded loops, drawn on authorization — not on confidence

Reversal of the earlier "no bounded retry" position, plus the in-scope repair added alongside it. Both were approved deliberately; do not silently re-tighten them.

| Loop | Cap | What it mutates | Escalates to |
|---|---|---|---|
| Re-run a red check, byte-identical | 1 | nothing | severe → STOP on the second red |
| Repair a `must-fix` inside the plan's declared `**Files:**` | 1 | only files the user authorized at Step 2 | severe → STOP if still `must-fix`, or if the repair needs a file outside the declared set |

**Why the original rejection was wrong.** It read "masks real failures" — but a flake written into the run log and the final review is the opposite of masked. The rejection conflated *suppressing* a signal with *recording* one. The real constraint was never "never re-run"; it was "never let a failure disappear," and logging satisfies that.

**Why the line sits at authorization, not at confidence.** The tempting formulation is "auto-fix when confident." That is unfalsifiable and expands under pressure — the same defect as a judged terminal in invariant 4(b). Authorization is checkable: a re-run changes zero bytes, and an in-scope repair changes only files the user named when approving the plan at Step 2. Everything past the declared `**Files:**` has no authorization behind it, which is exactly what `no-auto-fix` protects. That rule is unchanged; these two loops sit inside it, not around it.

**What motivated the change.** Both are the common mid-run death causes for an AFK run: one flaky test, or one `must-fix` on code the run itself just wrote, ends a multi-hour run and the user returns to nothing delivered. A driver that reliably dies before finishing a phase is not a conservative driver, it is a broken one. Read this together with invariant 4: 4 keeps the *policy* from drifting toward stopping; 5 keeps the *machinery* from doing the same.

**If you are about to remove these:** the failure you are worried about is already covered — a second red still stops, an out-of-scope repair still stops, diagnosis is still out of scope, and every loop iteration is in the run log. Removing them buys no safety and restores the death causes.

## Rejected enhancement ideas (and why)

Evaluated and rejected as over-design relative to the AFK user's intent (`/self-pacing` already implies: verified plan exists, long run expected, don't interrupt unless truly blocked):

- **Token budget / runaway cap** — contradicts "I expect a long run." AFK = long by intent. (If you are about to re-add this as "just a context check before continuing", read invariant 4(b)'s observed instance first — a context-occupancy gate is the judged terminal that section bans, and the driver already gets a measured `[ctx]` number without one.)
- **Scope-drift check at phase seams** — relies on the user editing the dev-guide mid-run, which they don't after authorizing and walking away.
- **Read-only diagnosis on failure cards** — the skill deliberately makes diagnosis the user's; auto-diagnosis AFK risks confident-wrong.
- **Wait-then-auto-handoff timer** — see invariant 3.
- ~~**Bounded transient-failure retry**~~ — **reversed 2026-08-06 with the owner's explicit approval; see invariant 5.** Kept listed rather than deleted: the original rejection ("masks real failures") is a reasonable-sounding argument that will be re-derived by the next reader, so the counter-argument needs to stay attached to it.
