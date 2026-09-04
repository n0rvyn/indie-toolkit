# afk Eval

## Trigger Tests

**Should trigger:**
- "/afk"
- "我出去一趟，你自己跑到 block 为止"
- "push this to the end while I'm out, don't ask me"
- "一直推到 block，重大决策才停"

**Should NOT trigger:**
- "写个计划" / "plan this" (use write-plan)
- "执行这个计划" with a verified plan file present (use execute-plan)
- "我们该做什么功能" (divergent — use brainstorm)
- Any request while the user is plainly at the keyboard and iterating turn-by-turn

## Output Assertions

**Step 1 — the setup is three lines and one refusal:**
- [ ] Emits `[目标]` / `[判据]` / `[范围]` before any other work
- [ ] `[判据]` is a runnable command or a concrete observation, not a disposition ("verify it works" fails this)
- [ ] The judge is RUN once before the run starts, and a judge that is already green stops the run with a statement of which case it is (goal already met vs. judge tests nothing)
- [ ] Cannot name a runnable judge → refuses and stops **at authorization time**, never after the user leaves. This is the only refusal the skill makes
- [ ] Writes NO plan file. Work that turns out to need a plan is a stop, not a branch that writes one

**Step 2 — pre-flight is conditional and correctly ordered:**
- [ ] Asks whether the run needs a physical device at all; a non-Apple / simulator-free run skips the entire step
- [ ] Device auto-lock is item 1 (the only item that survives the whole run; a probe cannot cover it)
- [ ] Checks wired vs `localNetwork` transport before the UI-test probe
- [ ] Probes with a real minimal UI test rather than consulting a fixed list of known dialogs
- [ ] ⛔ Never reinstalls the xctrunner as a remedy (that reinstall re-triggers the dialog it is meant to fix)
- [ ] Probe not constructable (no UI test target / no paired device) → reports at authorization time and CONTINUES without device coverage; does NOT refuse to start and does NOT create a UI test target

**Step 3 — one batch:**
- [ ] Every open question, the three lines, and the pre-flight result are presented in a single batch; only an explicit go proceeds

**Stop Policy:**
- [ ] Terminals are exactly the table's rows; "this is a good place to hand off" is explicitly not one
- [ ] `[判据]` red once → one re-run (same command, no file change between); red twice → stop
- [ ] Work outside `[范围]` → stop, not a judgment call
- [ ] "Option A is faster so the experience is better" is explicitly NOT a user-judgment stop
- [ ] Every stop invokes `dev-workflow:handoff` before the turn ends

**Hard Rules — the two mechanical gates (these are the reason the skill exists):**
- [ ] Done-gate: a terminal "done" carries the freshly-run `[判据]` raw output pasted into the report. A done-claim with no adjacent fresh command output fails this assertion
- [ ] No prose hand-back: ending a turn with 「你拍板」/「你决定」/「从哪个开始」 while already holding a view is prohibited; the model takes it, states the evidence, and marks what the user can overturn
- [ ] The prose rule is scoped to plain text as well as `AskUserQuestion` — the structured tool was never the leak
- [ ] The candidate check (N options circling one obstacle / resting on an unverified premise) qualifies a QUESTION and is explicitly not a licence to work around a FAILURE

**Artifacts:**
- [ ] Run log written incrementally to `.claude/afk/<slug>.md` in the same turn as each decision, never batched at the end
- [ ] Handoff doc via `dev-workflow:handoff` at every stop
- [ ] Writes NO review-report file (findings go in the final report)

**Cross-skill:**
- [ ] `handoff` SKILL.md's autonomous-run section triggers on `.claude/afk/<slug>.md` existing, not only on the self-pacing path
- [ ] `public-entry-policy.md` lists `afk` as a manual entry (never model-routed)
- [ ] `self-pacing` SKILL.md body-top carries the superseded marker pointing at `afk`
- [ ] `disable-model-invocation: true` present — the skill must never be auto-routed

## Redundancy Risk

Baseline: the base model plus the user's CLAUDE.md already drives long unattended stretches competently — measured, 271 of 283 sessions over 30 days shipped real work with no plan pipeline at all. This skill is NOT justified by adding structure. It is justified by three things the base model demonstrably does not do on its own:
1. front-loading human-required unblocks before the user leaves (device auto-lock alone killed real-device runs across ≥6 sessions),
2. the done-gate (one recorded run claimed completion while 35 of 50 test suites were red),
3. the prose hand-back ban (two recorded instances of handing back a decision the model had already made).

If a future model closes all three unprompted, this skill is redundant and should be deleted rather than kept for form.

Last tested model: —
Last tested date: —
Verdict: pending first real run
