---
name: afk
description: "Use when the user is stepping away and wants work driven to a stated end state on its own — '/afk', 'afk', '我出去一趟', '你自己跑', '一直推到 block', '推到头', 'run this while I'm out', 'push it to the end', \"don't ask me, just decide\". Sets up a native `/goal` run: distills the goal, proves the completion check can currently fail, clears the human-required unblocks that kill unattended Apple runs (device lock, wireless transport, on-device trust dialog, sudo), and hands back a ready-to-paste `/goal` line. For work whose END STATE is writable but whose ROUTE is not yet known — route-known work belongs in write-plan → execute-plan, and work whose end state cannot be written needs the user present. Not when: the user is at the keyboard iterating turn by turn; the work is divergent design exploration (use brainstorm); a verified plan exists and should be executed task-by-task (use execute-plan)."
disable-model-invocation: true
---

<!-- cost-posture: inherit (judgment — goal distillation, judge construction, and unblock triage are judgment calls; do NOT downgrade to sonnet/haiku per dev-workflow Skill Cost Posture rule) -->

## What this is

`/afk` is **setup, not a loop.** Claude Code already ships the loop: [`/goal`](https://code.claude.com/docs/en/goal) sets a completion condition and, after every turn, **a separate fast model** — not the one doing the work — judges whether it holds, and starts another turn if it does not. That independent grader is better than anything a prompt can do by self-report, so this skill does not reimplement it.

What `/goal` does not do is everything that has to happen **before** the user walks away. That is this skill:

1. turn a vague goal into a condition an evaluator can actually judge,
2. prove the completion check can currently **fail**,
3. clear the human-required unblocks that kill unattended runs,
4. hand back the `/goal` line to paste.

⚠️ **The model cannot type a slash command.** Step 4 ends with a line for the user to paste. That is a harness constraint, not a design choice.

## Which of the three paths is this work on

Two questions, each answered by **trying to write something**, not by judging:

| | Route already known | Route not yet known |
|---|---|---|
| **End state can be written** | `write-plan` → `verify-plan` → `execute-plan` | **`/afk`** |
| **End state cannot be written** | — | **The user must stay.** `brainstorm`, or plain conversation |

- "Can the end state be written?" = can you write `[判据]` below. Write it; if you cannot, that is the answer.
- "Is the route known?" = can you list the task sequence. Same test.

Measured basis (30 days to 2026-09-04, this account's transcripts): pipeline density tracks **work shape**, not project age — scoped feature/phase work runs through the pipeline even on a 10-month-old project, while open-ended R&D and deep debugging run outside it even on a 3-week-old one. Project maturity is the wrong variable; whether the end state is writable is the right one.

## Step 1 — Three lines, and one refusal

```
[目标] {one sentence — what is true when this is done}
[判据] {the command or observation that proves it — runnable right now}
[范围] {the surface this may touch — a directory, a module, a target}
```

- **Run `[判据]` once, before anything else. It must come back red.** Already green means either the goal is already met or the judge tests nothing — say which and stop. A judge nobody has seen fail is not a judge.
- **If no runnable judge exists, say so now and stop.** This is the only refusal `/afk` makes, and it has to happen while the user is still here.
- **`[范围]` is the blast radius**, and it goes into the goal condition as a constraint. Reaching outside it is a stop.
- **Do not write a plan file, and do not invoke `write-plan`.** Nesting it would just relocate the precondition this skill exists to drop. If mid-run the work turns out to need a plan, stop and say so — a clean terminal.

## Step 2 — Clear what only a human can clear

**First: does this run need a physical device at all?** No — non-Apple repo, no device work — skip this step entirely.

If it does, in this order:

1. **Auto-lock off.** An idle device locks itself and `xcodebuild test` dies on `Unlock iPhone to Continue` → `code 74`. AFK *causes* this: the user walking away is the trigger. A probe cannot cover it — passing now says nothing about two hours from now, which is why this is first and why it is a request to the user rather than a check.
2. **Wired, not `localNetwork`.** The wireless tunnel resets every ~18s and kills the long-lived UI-test driver while short unit tests survive.
3. **One minimal real-device UI test as a probe**, to force out whatever on-device trust/automation dialog exists right now. Probe, do not consult a list of known dialogs — a list goes stale, a probe surfaces today's.
4. ⛔ **Never reinstall the xctrunner as a remedy.** That reinstall re-triggers the very dialog it is meant to fix, and the loop is invisible from inside the run.

**Probe not constructable** (no UI test target, no paired device): say so now and **continue without device coverage**. Do not refuse to start, and do not create a UI test target to satisfy the probe — that scope is not yours to take.

Also name any other human-required unblock this run will touch: a `sudo` password, a simulator boot (which needs explicit approval), a credential near expiry.

## Step 3 — Hand over the `/goal` line

Present the three lines, the judge's red result, the pre-flight outcome, and **every open question in one batch** — this is the last moment the user is reliably present.

Then give the line to paste. Build the condition from the three things `/goal` asks for:

- **one measurable end state** — from `[目标]`
- **a stated check** — from `[判据]`, naming the command whose output the evaluator will read
- **constraints that matter** — from `[范围]`, plus anything that must not change

```
粘这行然后走：
/goal {end state}；证据是 {command} 的原始输出；不改 {范围} 之外的文件
```

⚠️ **The evaluator reads the transcript; it does not run commands or read files.** So the condition must be something Claude's own output can demonstrate, and the run must actually put that output in the transcript — which is what the done-gate below is for. Also worth adding to the condition when the work could run long: `or stop after N turns`.

Tell the user two things they may not know: `/goal` only runs unattended in **auto mode** (otherwise it still asks before unapproved tool calls), and it survives `--continue` / `--resume`.

## During the run

Route is yours — tools, order, whether to use agents, when to refactor. These are the whole constraint.

**Two gates. Both are here because the failure is on record, not because of any belief about what models can or cannot do.**

- **A done-claim carries freshly-run output, or it is not a done-claim.** Before reporting the goal met, re-run `[判据]` and paste its raw output. Not the remembered result, not a summary — the output, from a run that just happened. This is also what feeds the evaluator: it can only judge what is in the transcript, so a summary of a passing test is exactly the input a false success needs. *(On record: a run reported completion in the same message that admitted 35 of 50 test suites were failing, using "not introduced this session" as the reason not to fix them.)*

- **No prose hand-back once you have a view.** About to end a turn with 「两件事要你拍板」/「你决定」/「从哪个开始？」 while you already have an opinion? That is not a decision point, it is outsourcing a judgment you have made. Take it, say what you took and on what evidence, mark what the user can overturn. This applies to plain text, not just `AskUserQuestion` — the structured tool has never been the leak; 16 deep-read invocations were all legitimate must-ask cases. *(On record: `我倾向做，但这个风险归你判断`.)*

  ⚠️ **Before any stop, check the candidates.** If the options you are about to hand over all circle one obstacle, or all rest on a premise nobody verified ("these two can't be done in the same pass", "A must precede B"), that is not a choice — it is a report that the work is a layer too low. Falsify the premise; the choice usually disappears. This qualifies a *question*. It is never a licence to work around a *failure*.

**Stop and end the turn for these** — `/goal` will re-evaluate on the user's return, so a stop is not the end of the goal:

| Situation | Why |
|---|---|
| The work would touch something outside `[范围]` | Past that line there is no authorization |
| An irreversible or outward-facing action | Deleting data, migrating, publishing, changing a shipped interface |
| A difference only the user can judge | A default, wording, an interaction shape, a layout, where technical fact picks no winner. ⛔ "Option A is faster so the experience is better" is **not** this — that is a technical fact; rank it yourself |
| The instruction admits ≥2 readings | Guessing costs a rebuild; asking costs a sentence |
| The work turns out to need a plan | Say so and stop; route to `write-plan` |
| `[判据]` red twice — same command, no file change between | One re-run separates a flake; a second red needs diagnosis, which needs the user |

**If none of these fires, keep going.** "This is a good place to hand off" is not a terminal — it is a self-assessment, unfalsifiable and always available.

**Every stop writes the handoff first**: invoke `dev-workflow:handoff`, then end the turn. Handoff docs are the one artifact class that reliably gets read again, which is why the transfer goes there.

**Log every self-made decision** to `.claude/afk/<slug>.md` in the turn it happens — a batched write at the end loses the log to a context reset. Anything decided, deferred, or worked around goes in it and in the final report. A silent auto-decision is what makes a finished run untrustworthy.

**No review-report files.** Findings go in the final report, where they are read. *(Measured: review report files are written ~6× more often than they are read back; the findings that reached a human did so through the returning agent's text, not the file.)*

<!-- OPEN, deliberately unresolved: whether a terminal /afk stop should dispatch fresh-context review agents (correctness / test-coverage / breaking-change). The measured case for it: review findings were real, and the user's own note reads 「两次都是派出去的审查 agent 抓到的，我自己跑测试全绿、一点感觉都没有」. The measured case against: review-execution is a link in the run-phase chain and may carry upstream preconditions that make it unsound standing alone. Do NOT wire this up before that dependency question is answered. -->

## Artifacts

| Artifact | Path | When |
|---|---|---|
| Run log | `.claude/afk/<slug>.md` | incrementally, every self-made decision |
| Handoff doc | `docs/06-plans/HANDOFF-YYYY-MM-DD-HHMM.md` (via `dev-workflow:handoff`) | at every stop |

The code plus these two are the source of truth. Chat is not — on a cold resume there is no chat.

## Relationship to the rest of the flow

- **`/goal`** (native) owns the loop and the completion judgment. This skill owns the setup and hands off to it.
- **`write-plan` → `verify-plan` → `execute-plan`** owns route-known work. `/afk` does not invoke it and does not replace it; the table above routes between them.
- **`self-pacing`** is superseded by this skill, and kept only for driving an already-verified multi-phase dev-guide across seams.
- **`fix-bug`** remains the diagnostic protocol for a reported defect. `/afk` does not invoke it and runs no formal diagnosis — though the layer question it enforces (what did the existing design solve; is this patch treating a symptom) is the same question the ⚠️ above asks before a stop.
- Nothing else is modified by this skill.
