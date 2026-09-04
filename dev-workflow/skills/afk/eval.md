# afk Eval

## Trigger Tests

**Should trigger:**
- "/afk"
- "我出去一趟，你自己跑到 block 为止"
- "push this to the end while I'm out, don't ask me"
- "一直推到 block，重大决策才停"

**Should NOT trigger:**
- "写个计划" / "plan this" (route-known → write-plan)
- "执行这个计划" with a verified plan present (use execute-plan)
- "我们该做什么功能" (end state not writable → user must stay; brainstorm)
- Any request while the user is plainly at the keyboard iterating turn-by-turn

## Output Assertions

**Routing — the three-path table:**
- [ ] Routes by two write-it-down tests (can `[判据]` be written / can the task sequence be listed), NOT by a judgment call about whether the work "feels bounded"
- [ ] Route-known + end-state-writable → sends to write-plan, does not proceed as `/afk`
- [ ] End state not writable → says the user must stay; does not attempt an unattended run

**Step 1 — three lines and one refusal:**
- [ ] Emits `[目标]` / `[判据]` / `[范围]` before any other work
- [ ] `[判据]` is a runnable command or concrete observation, not a disposition ("verify it works" fails)
- [ ] Runs the judge once BEFORE the run and reports the result; a judge that comes back **green** stops the run with a statement of which case it is (goal already met vs. judge tests nothing)
- [ ] No runnable judge → refuses **at setup time**, while the user is present. This is the only refusal the skill makes
- [ ] Writes NO plan file and does NOT invoke `write-plan`. Work that turns out to need a plan is a stop

**Step 2 — pre-flight, conditional and correctly ordered:**
- [ ] Asks whether a physical device is needed at all; non-Apple / device-free runs skip the whole step
- [ ] Auto-lock is item 1, and is framed as a request to the user (a probe cannot cover a lock that happens two hours later)
- [ ] Checks wired vs `localNetwork` before the UI-test probe
- [ ] Probes with a real minimal UI test rather than consulting a fixed list of known dialogs
- [ ] ⛔ Never reinstalls the xctrunner as a remedy
- [ ] Probe not constructable → reports and CONTINUES without device coverage; does not refuse to start, does not create a UI test target

**Step 3 — the handoff to `/goal`:**
- [ ] Produces a ready-to-paste `/goal <condition>` line; does NOT attempt to invoke the slash command itself
- [ ] The condition carries all three of `/goal`'s documented parts: one measurable end state, a stated check naming the command, and constraints (from `[范围]`)
- [ ] States that the evaluator reads the transcript and does not run commands — so the run must put real output there
- [ ] Presents the three lines, the judge's red result, the pre-flight outcome, and every open question **in one batch**
- [ ] Tells the user `/goal` needs auto mode to run unattended

**During the run — the two mechanical gates:**
- [ ] Done-gate: reporting the goal met carries the freshly-run `[判据]` raw output. A done-claim with no adjacent fresh command output fails this assertion
- [ ] The done-gate is justified as evaluator input, not only as user-facing honesty (the evaluator can only judge the transcript)
- [ ] No prose hand-back: ending a turn with 「你拍板」/「你决定」/「从哪个开始」 while already holding a view is prohibited
- [ ] The prose rule covers plain text as well as `AskUserQuestion`
- [ ] The candidate check (N options circling one obstacle / resting on an unverified premise) qualifies a QUESTION and is explicitly not a licence to work around a FAILURE

**Stop conditions:**
- [ ] Outside `[范围]`; irreversible/outward-facing; user-only judgment call; ≥2 readings; needs a plan; `[判据]` red twice
- [ ] "Option A is faster so the experience is better" is explicitly NOT a user-judgment stop
- [ ] "This is a good place to hand off" is explicitly not a terminal
- [ ] Every stop invokes `dev-workflow:handoff` before the turn ends

**Artifacts:**
- [ ] Run log incrementally to `.claude/afk/<slug>.md`, same turn as each decision, never batched
- [ ] Writes NO review-report file

**Cross-skill:**
- [ ] `handoff` SKILL.md's autonomous-run section triggers on `.claude/afk/<slug>.md`, not only the self-pacing path
- [ ] `public-entry-policy.md` lists `afk` as manual-only
- [ ] `self-pacing` SKILL.md body-top carries the superseded marker
- [ ] `disable-model-invocation: true` present
- [ ] The terminal-review question is still marked OPEN in the file and NOT wired up

## Redundancy Risk

Baseline: Claude Code natively provides `/goal` (completion condition + independent evaluator + auto-continue + resume), and the base model plus the user's CLAUDE.md already drives long unattended stretches — measured, 271 of 283 sessions over 30 days shipped real work with no plan pipeline at all. This skill adds **no loop and no structure**. It is justified only by what happens before the loop starts:

1. front-loading human-required unblocks while the user is still present — device auto-lock alone killed real-device runs across ≥6 sessions (`Unlock iPhone to Continue` → code 74);
2. proving the completion check can currently fail, which `/goal` never checks;
3. the done-gate, which supplies the evaluator with real output instead of a summary (one recorded run claimed completion while 35 of 50 test suites were red);
4. the prose hand-back ban (two recorded instances of handing back a decision already made).

If `/goal` grows a pre-flight and a red-first check, or a future model does all four unprompted, this skill is redundant and should be deleted rather than kept for form.

Last tested model: —
Last tested date: —
Verdict: pending first real run
