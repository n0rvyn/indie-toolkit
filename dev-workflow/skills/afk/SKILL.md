---
name: afk
description: "Use when the user is stepping away and wants a GOAL driven to completion autonomously — '/afk', 'afk', '我出去一趟', '你自己跑', '一直推到 block', '推到头', 'run this while I'm out', 'push it to the end', \"don't ask me, just decide\". Goal-oriented rather than plan-oriented: it needs a goal, a runnable convergence signal, and a surface — NOT a written plan or dev-guide. Stops only for what a human must supply: an irreversible action, a difference only the user can judge, an instruction with two readings, a signal red twice, or work that turns out to need a plan. Not when: the user is at the keyboard (just work normally); the work is divergent design exploration (use brainstorm); a verified plan already exists and should be executed task-by-task (use execute-plan)."
disable-model-invocation: true
---

<!-- cost-posture: inherit (judgment + orchestration — goal extraction, severity classification, loop control; do NOT downgrade to sonnet/haiku per dev-workflow Skill Cost Posture rule) -->

## What this is

There are two ways to drive coding work. **Plan-oriented** — `write-plan` → `verify-plan` → `execute-plan` — settles everything up front and executes a written contract. **Goal-oriented** — this skill — fixes a goal and a way to know it is met, then leaves the route to the model.

`/afk` is the goal-oriented one. It exists because a plan is not what makes unattended work safe; the **convergence signal** is. A plan is one way of writing that signal down. It is not the only way, and demanding one turns a two-minute goal into a twenty-minute document.

Latitude is the point: *how* to reach the goal is the model's call, and second-guessing that is how a human's own blind spots get installed as constraints. The two gates in `## Hard Rules` are not latitude — they are there because those exact failures are on record.

## Step 1 — Fix three lines. That is the entire setup.

Before anything runs, write these and show them:

```
[目标] {one sentence — what is true when this is done}
[判据] {the command or observation that shows it — runnable right now}
[范围] {the surface this may touch — a directory, a module, a target}
```

- **`[判据]` is the strict part, and the only refusal this skill makes.** If you cannot name something runnable that would show the goal met, say so **now** and stop — while the user is still here, never after they have gone.
- **Run the judge once before anything else.** It must be able to come back **red**. Already green means either the goal is already met or the judge tests nothing; say which and stop. (A judge nobody has seen fail is not a judge — same rule as any other checker.)
- **`[范围]` replaces the plan's `**Files:**`.** It is the blast radius the user authorizes by saying go. Reaching outside it is a stop, not a judgment call.
- **Do not write a plan file.** If mid-run you conclude the work genuinely needs one, stop and say so — that is a clean terminal, not a failure.

## Step 2 — Clear what only a human can clear (while they are still here)

Every unattended run dies on the first thing that needs a hand. Pull those forward.

**Ask first: does this run need a physical device at all?** If no — non-Apple repo, simulator-free, pure logic — skip the rest of this step entirely.

If it does, in this order:

1. **Auto-lock off.** An idle device locks itself and `xcodebuild test` dies on `Unlock iPhone to Continue` → `code 74`. AFK *causes* this — the user walking away is the trigger. A probe cannot cover it: passing now says nothing about two hours from now. This is the only item that survives the whole run, so it goes first.
2. **Wired, not `localNetwork`.** The wireless debug tunnel resets every ~18s and kills the long-lived UI-test driver while short unit tests survive. Check the transport; if wireless, ask for the cable.
3. **One minimal real-device UI test as a probe** — to force out whatever on-device trust/automation dialog exists right now. Probe, do not consult a checklist: a checklist goes stale, a probe surfaces today's dialog.
4. ⛔ **Never reinstall the xctrunner as a remedy.** That reinstall re-triggers the very authorization dialog it is supposed to fix, and the loop is invisible from inside the run.

**If the probe cannot be built at all** (no UI test target, no paired device): say so at authorization time and **continue without device coverage** — do not refuse to start, and do not create a UI test target to satisfy the probe. That scope is not yours to take.

Also surface any other human-required unblock this run will touch: a `sudo` password, a simulator boot (which needs explicit approval), an expiring credential.

## Step 3 — Authorize, asking everything at once

Show the three lines from Step 1, the pre-flight result from Step 2, and **every open question in one batch**. This is the only moment the user is reliably present; a question saved for later is a question that ends the run.

Only an explicit go proceeds.

## Step 4 — Run

Work the goal. Log every self-made decision to `.claude/afk/<slug>.md` as it happens, in the same turn — a batched write at the end loses the log to a context reset.

Route is yours. Tools, order, whether to use agents, when to refactor — all yours. The rules below are the whole constraint.

## Stop Policy

The run ends at green, or at one of these. Nothing else is a terminal.

| Situation | Why it is a stop |
|---|---|
| `[判据]` red twice — same command, no file change between the two runs | One re-run distinguishes a flake; a second red is a real failure and diagnosis needs the user |
| The work would touch something outside `[范围]` | Past that line there is no authorization |
| An irreversible or outward-facing action | Deleting data, migrating, publishing, changing a shipped interface |
| A difference only the user can judge | A default, wording, an interaction shape, a layout — where technical fact does not pick a winner. ⛔ "This option is faster so the experience is better" is **not** this; that is a technical fact, rank it yourself |
| The instruction admits ≥2 readings | Guessing costs a rebuild; asking costs a sentence |
| The work turns out to need a written plan | Say so and stop — a clean terminal |

**If no row fires, continue.** There is no default stop, and "this is a good place to hand off" is not a terminal — it is a self-assessment, unfalsifiable and always available.

**Every stop writes the handoff before the turn ends**: invoke `dev-workflow:handoff`, then end the turn so the idle notification fires. Handoff docs are the one artifact class that reliably gets read again; that is why the transfer goes there rather than into a card that grows into a document.

## Hard Rules

Two gates. Both exist because the failure is on record, not because of any belief about what models can do.

- **The done-gate — a done-claim carries fresh output or it is not a done-claim.** Before writing "done" / "推到头了" / "全绿", re-run `[判据]` and paste its raw output into the report. Not the remembered result, not a summary: the output, from a run that just happened. *(On record: a run reported completion while the same message admitted 35 of 50 test suites were failing, using "not introduced this session" as the reason not to fix them.)*

- **No prose hand-back once you have an opinion.** If you are about to end a turn with 「两件事要你拍板」/「你决定」/「从哪个开始？」 and you **already have a view**, that is not a decision point — it is outsourcing a judgment you have already made. Take it, say what you took and on what evidence, and mark what the user can overturn. Applies to plain text, not just `AskUserQuestion` — the structured tool has never been the leak. *(On record: `我倾向做，但这个风险归你判断`.)*

  ⚠️ **Before any stop, check the candidates.** If the options you are about to hand over are all circling one obstacle, or all resting on a premise nobody verified ("these two can't be done in the same pass", "A must precede B"), that is not a choice — it is a report that the work is a layer too low. Falsify the premise; the choice usually disappears. This qualifies a *question*; it is never a licence to work around a *failure*.

Three smaller ones:

- **Ask once, ask everything.** A second stop costs another handoff doc and another return trip.
- **Every self-made decision is visible.** Anything decided, deferred, or worked around appears in the run log and the final report. A silent auto-decision is the failure mode that makes a finished run untrustworthy.
- **No review-report files.** Findings go in the final report where they are read. *(Measured: review report files are written ~6× more often than they are read back; the findings that reached a human did so through the returning agent's text, not the file.)*

## Artifacts

| Artifact | Path | When |
|---|---|---|
| Run log | `.claude/afk/<slug>.md` | incrementally, every self-made decision |
| Handoff doc | `docs/06-plans/HANDOFF-YYYY-MM-DD-HHMM.md` (via `dev-workflow:handoff`) | at every stop |

Source of truth is the code plus these two. Chat is not authoritative — on a cold resume there is no chat.

## Relationship to the rest of the flow

- **`execute-plan`** owns the plan-oriented path. A verified plan that should be executed task-by-task goes there, not here.
- **`self-pacing`** is superseded by this skill; it required a verified plan or dev-guide up front, which is the requirement this skill exists to drop.
- **`fix-bug`** stays the diagnostic protocol for a reported defect. `/afk` does not invoke it and does not run its own formal diagnosis — but the layer question it enforces (what did the existing design solve, and is this patch treating a symptom) is the same question the ⚠️ above asks before a stop.
- Nothing else is modified by this skill.
