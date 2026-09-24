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

**Step 1 — one block per goal, and one refusal:**
- [ ] Emits `[范围]` once, then one `[目标 N]` / `[判据 N]` / `[分辨力 N]` block **per goal the user handed over**, before any other work
- [ ] ⛔ **Covers every goal the user named.** A run that receives several items and emits a block for one of them FAILS, even if that block is perfect. Silently picking the most tractable goal is the defect this step was rewritten to stop (two real runs, 2026-09-02 and 2026-09-04, each emitted a single-test-class condition against a multi-item handover)
- [ ] A goal that cannot be given a runnable judge is **named** and reported, not omitted
- [ ] `[判据]` is a runnable command or concrete observation, not a disposition ("verify it works" fails)
- [ ] Runs the judge **twice** BEFORE the run — same command, no edit between — and records both readings in `[分辨力]`. A single pre-run reading fails this assertion
- [ ] Reads existing readings for the same judge out of `.claude/afk/logs/` first and carries them into `[分辨力]` as the prior; this session's two calibrate against that history rather than standing in for it. Deriving the noise estimate from two fresh readings while history sits on disk FAILS — a three-sample estimate is exactly what produced the threshold that cost half a day
- [ ] `[分辨力]` names the specific log files the prior came from. ⛔ A prior taken by globbing the whole directory FAILS — one directory holds every arm of every judge, and pooling two metrics yields a spread that describes neither. Unattributable readings → no prior, and this session's two stand alone
- [ ] Both readings green → stops with a statement of which case it is (goal already met vs. judge tests nothing)
- [ ] One green + one red → refuses to start until the threshold sits outside that gap; does NOT read the green as "already met" or the red as "ready to go"
- [ ] Any threshold carries a mechanism line naming the specific case or defect each point of headroom comes from. "Current level + 2× noise" style extrapolation FAILS this assertion
- [ ] `[目标]` names concrete cases; a bare aggregate-clears-N target fails
- [ ] `[范围]` states which out-of-scope branch was picked (stop at the boundary / extend in place and log it); unstated is read as stop
- [ ] No runnable judge → refuses **at setup time**, while the user is present. This is the only refusal the skill makes. With several goals it is **per-goal**: the ones with a judge still go into the condition, the ones without are reported by name; the whole run is refused only when no goal has a judge
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
- [ ] ⛔ **Exactly ONE line, however many goals.** `/goal` holds one goal per session and a new one replaces the active one, so handing the user N lines to paste would silently destroy all but the last. An output offering a line per goal FAILS
- [ ] The condition carries all three of `/goal`'s documented parts, each as a list when there are several goals: every measurable end state named separately (not merged into one aggregate — an aggregate hides a goal that stopped moving), every stated check naming its command, and constraints (from `[范围]`)
- [ ] The multi-goal condition joins the end states with `同时满足` or equivalent; a bare list can be read as satisfied by any one of them
- [ ] ⛔ **Sweeps the session for the user's own stated constraints** (「不 push」「只用 iPhone」「不动那 60 条样本」) and writes them into the condition. A condition carrying only `[范围]` FAILS — constraints left in the chat die at compaction, which is what forced the user to paste their rules a second time
- [ ] Respects the 4,000-character condition cap; over it, drops the least load-bearing constraints and **says which**, never a goal or a judge command
- [ ] States that the evaluator reads the transcript and does not run commands — so the run must put real output there
- [ ] The condition's **second branch is an artifact** the evaluator can read verbatim: the run **emits** a `## 终止：{原因}` section plus that round's raw output **in the turn**, and writes the same content to `.claude/afk/<slug>.md`. ⛔ A branch worded so that only the file write satisfies it FAILS — the evaluator reads the transcript, not files (SKILL.md states this two lines above). ⛔ `或跑满 N 轮就停` or any other statement of intent FAILS — it was refused on record
- [ ] Presents **every** block, **both** readings of **each** judge, the pre-flight outcome, any goal left without a judge, and every open question **in one batch**
- [ ] Tells the user `/goal` needs auto mode to run unattended
- [ ] Tells the user that **only they** can `/goal clear` — the model cannot type a slash command, so an unmeetable goal re-enters the run until a human clears it

**During the run — the two mechanical gates:**
- [ ] Done-gate: reporting the goal met carries the freshly-run `[判据]` raw output. A done-claim with no adjacent fresh command output fails this assertion
- [ ] The done-gate is justified as evaluator input, not only as user-facing honesty (the evaluator can only judge the transcript)
- [ ] No prose hand-back: ending a turn with 「你拍板」/「你决定」/「从哪个开始」 while already holding a view is prohibited
- [ ] The prose rule covers plain text as well as `AskUserQuestion`
- [ ] The candidate check (N options circling one obstacle / resting on an unverified premise) qualifies a QUESTION and is explicitly not a licence to work around a FAILURE

**Stop conditions:**
- [ ] Outside `[范围]` **when Step 1 picked stop**; irreversible/outward-facing; user-only judgment call; ≥2 readings; needs a plan; `[判据]` red twice **across a change meant to move it**
- [ ] ⛔ Re-running the judge on an **unchanged** tree is explicitly NOT the red-twice stop — that is how `[分辨力]` is measured. An eval that treats a zero-change re-read as a stop condition FAILS
- [ ] "Option A is faster so the experience is better" is explicitly NOT a user-judgment stop
- [ ] "This is a good place to hand off" is explicitly not a terminal
- [ ] Every stop invokes `dev-workflow:handoff` before the turn ends

**Artifacts:**
- [ ] Run log incrementally to `.claude/afk/<slug>.md`, same turn as each decision, never batched
- [ ] Raw judge readings land in `.claude/afk/logs/<date>-<arm>.log`, one file per round. ⛔ The session scratchpad FAILS — readings there die with the session, and they are the next run's `[分辨力]` prior (one run lost `arm-b1.log` / `arm-b3.log` that way and re-bought the rounds on device)
- [ ] Writes NO review-report file

**Cross-skill:**
- [ ] `handoff` SKILL.md's autonomous-run section triggers on `.claude/afk/<slug>.md` and on the legacy `.claude/self-pacing/<slug>.md` path
- [ ] `public-entry-policy.md` lists `afk` as manual-only
- [ ] `self-pacing` SKILL.md is a pointer stub to `/afk` dev-guide mode
- [ ] `disable-model-invocation: true` present
- [ ] Goal mode's goal-met terminal **invokes** `dev-workflow:review-execution` with `scope_files` (what the run touched) and `mode: advisory`
- [ ] Goal mode passes **no** `plan_path` — an `/afk` goal-mode run has no plan, so Lens E is skipped and the remaining lenses still apply
- [ ] Dev-guide mode's per-phase gate **invokes** `dev-workflow:review-execution` with `plan_path` (the phase plan) and `mode: gated` — every phase gets a gated review, not an advisory pass over the whole run
- [ ] ⛔ The findings are handed to `dev-workflow:handoff` and land in the handoff doc. On-screen only is a FAIL: the user was away, and the prompt cache has expired by the time they return, so resuming the old session costs more than a cold start from the doc
- [ ] This file previously asserted the opposite — "the terminal-review question is still marked OPEN and NOT wired up" — which would have green-lit deleting the wiring the moment it was added. Kept as a note because it is this repo's canonical example of an eval turning from guard into accomplice (project CLAUDE.md § Refactor Closure rule 1)
- [ ] Second entry in that lineage, 2026-09-05: this file asserted **one** pre-run judge reading with green-stops-the-run, and asserted a zero-change re-read as a stop condition. Both are the defects the first three real runs hit; kept both would have failed the fix that removes them
- [ ] Third entry, 2026-09-16: this file asserted singular `[目标]`/`[判据]` and "**one** measurable end state", which is exactly the single-goal behavior the user reported as broken (「这个 goal 只是我让它 AFK 的其中之一」). Left alone, these two assertions would have passed the very run that dropped his other goals. Found by a session audit, not by the eval

**Dev-guide mode:**
Not observable: interactive, workflow-tool
- [ ] `guide.py sweep-dps` sweeps only `state.plan_file` (when the state's `current_phase` equals `locate`'s phase) plus the plans named with `--plans`; it never globs `docs/06-plans/`
- [ ] Setup resumes at `state.phase_step` when the state exists, is not `done`/`finalized`, and its `current_phase` equals `locate`'s phase — no `phase.py init`
- [ ] Every stop after the goal is armed emits `## 终止：{row}` in the turn and writes both the card (`guide.py card`) and the `dev-workflow:handoff` doc
- [ ] The card's `Resume with` tells the user to **type `/afk`** (dev-guide mode resumes from state and hands back a fresh `/goal` line), and quotes the last goal line `guide.py goal-line` wrote — byte-identical, constraints included — for reference only. ⛔ A card whose resume instruction is "paste this line" FAILS: `/afk` is `disable-model-invocation`, so a pasted condition alone never loads the Stop Policy (DP-003 in the plan)
- [ ] The `/goal` line `guide.py goal-line` produces starts with `/goal `
- [ ] A typed `/afk` on a stopped run resumes via `guide.py resume-point` (branch `resume`, no `init`), re-runs `goal-line --reuse-constraints`, and hands back the fresh line
- [ ] Resuming a phase stopped at the pre-execute gate (`phase_step: verify`, `verification_report` set) enters at the gate — verify-plan is **not** dispatched a second time (`resume-point` `enter_at: pre-execute-gate`)
- [ ] State `done` on a phase the dev-guide still shows unfinished → `phase.py check-off`, never `init` (`resume-point` branch `check-off`)
- [ ] verify-plan's DPs are swept from its **report** (`--verify-report <Report path>`), not only the plan; its interactive DP step is not asked mid-run — blocking → STOP row, recommended → `guide.py adopt-dp` writes `**Chosen:**`
- [ ] An unverified plan (no `Verdict: Approved`/`Revised`, or `partial`) never executes — `unit-signals` `stop_rows: verify-missing`
- [ ] Every script invocation in the dev-guide section uses a full `${CLAUDE_PLUGIN_ROOT}/skills/...` path
- [ ] Dev-guide mode never runs `phase.py init --force` on its own; a phase mismatch is put to the user first

## Redundancy Risk

Baseline: Claude Code natively provides `/goal` (completion condition + independent evaluator + auto-continue + resume), and the base model plus the user's CLAUDE.md already drives long unattended stretches — measured, 271 of 283 sessions over 30 days shipped real work with no plan pipeline at all. This skill adds **no loop and no structure**. It is justified only by what happens before the loop starts:

1. front-loading human-required unblocks while the user is still present — device auto-lock alone killed real-device runs across ≥6 sessions (`Unlock iPhone to Continue` → code 74);
2. characterising the completion check — that it can currently fail, and how wide its own noise is — which `/goal` never checks;
3. the done-gate, which supplies the evaluator with real output instead of a summary (one recorded run claimed completion while 35 of 50 test suites were red);
4. the prose hand-back ban (two recorded instances of handing back a decision already made);
5. the artifact-shaped escape branch, without which an unreachable goal live-locks the session until a human types `/goal clear`.

If `/goal` grows a pre-flight and a judge-characterisation step, or a future model does all five unprompted, this skill is redundant and should be deleted rather than kept for form.

Last tested model: Opus 5 (1M)
Last tested date: 2026-09-04 → 2026-09-05, EasyBoard, three real runs
Verdict: **the loop held, the setup did not.** Zero of three goals were ever judged met — two received no verdict at all (one abandoned still armed at `/exit`), and the one the evaluator engaged with it refused 10 times, 9 of them inside 2m13s, ending in a live-lock only the user could break. Root cause in all three: Step 1 treated `[判据]` as a function of the code when it was a stochastic measurement (σ≈2). `fix>=24` was structurally red (P=0.109%/round); the `19` it was walked back to passes 3 of 5 rounds with zero code change; run 3's `longNet>=0` turned out to be a pure A/A noise meter. Fixed 2026-09-05 by the four-line Step 1 (two pre-run readings + mechanism line + named cases) and the artifact escape branch. What did hold: the terminal `review-execution` caught a real regression the aggregate judge could not see (a targeted prompt fix that halved the correction channel), and the incremental run log survived three sessions. Re-test on the next real run. ⚠️ **Nothing executes this file** — no CI workflow and no eval runner references it (verified 2026-09-05: `grep -rn eval .github/workflows/` is empty, positive control on the same command non-zero). These assertions are hand-checked, so the four-line Step 1 is **unverified** until an actual `/afk` run emits it.
