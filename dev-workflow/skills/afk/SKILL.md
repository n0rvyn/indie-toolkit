---
name: afk
description: "Use when the user is stepping away and wants work driven to a stated end state on its own — '/afk', 'afk', '我出去一趟', '你自己跑', '一直推到 block', '推到头', 'run this while I'm out', 'push it to the end', \"don't ask me, just decide\". Also use when a verified multi-phase dev-guide exists and needs driving across phase seams — dev-guide mode. Sets up a native `/goal` run: distills **every** goal handed over (not the most tractable one), characterises each completion check (proves it can currently fail, and measures its own noise so the threshold is not drawn inside it), clears the human-required unblocks that kill unattended Apple runs (device lock, wireless transport, on-device trust dialog, sudo), and hands back **one** ready-to-paste `/goal` line covering all of them plus the constraints the user stated in session — `/goal` holds one goal per session, so a second pasted line would replace the first. For work whose END STATE is writable but whose ROUTE is not yet known — route-known work belongs in write-plan → execute-plan, except a verified dev-guide, which dev-guide mode drives, and work whose end state cannot be written needs the user present. Not when: the user is at the keyboard iterating turn by turn; the work is divergent design exploration (use brainstorm); a verified plan exists and should be executed task-by-task (use execute-plan)."
disable-model-invocation: true
effort: xhigh
---

<!-- cost-posture: inherit (judgment — goal distillation, judge construction, and unblock triage are judgment calls; do NOT downgrade to sonnet/haiku per dev-workflow Skill Cost Posture rule) -->

## What this is

`/afk` is **setup, not a loop.** Claude Code already ships the loop: [`/goal`](https://code.claude.com/docs/en/goal) sets a completion condition and, after every turn, **a separate fast model** — not the one doing the work — judges whether it holds, and starts another turn if it does not. That independent grader is better than anything a prompt can do by self-report, so this skill does not reimplement it.

What `/goal` does not do is everything that has to happen **before** the user walks away. That is this skill:

1. turn a vague goal into a condition an evaluator can actually judge,
2. characterise the completion check — prove it can currently **fail**, and measure its own noise before drawing a line on it,
3. clear the human-required unblocks that kill unattended runs,
4. hand back the `/goal` line to paste.

⚠️ **The model cannot type a slash command.** Step 4 ends with a line for the user to paste. That is a harness constraint, not a design choice.

## Which of the three paths is this work on

Two questions, each answered by **trying to write something**, not by judging:

| | Route already known | Route not yet known |
|---|---|---|
| **End state can be written** | `write-plan` → `verify-plan` → `execute-plan` | **`/afk`** |
| **End state cannot be written** | — | **The user must stay.** `brainstorm`, or plain conversation |
| **End state = the dev-guide's remaining phases complete** | route known (a verified dev-guide exists) → **`/afk` dev-guide mode** | — |

- "Can the end state be written?" = can you write `[判据]` below. Write it; if you cannot, that is the answer.
- "Is the route known?" = can you list the task sequence. Same test.

Measured basis (30 days to 2026-09-04, this account's transcripts): pipeline density tracks **work shape**, not project age — scoped feature/phase work runs through the pipeline even on a 10-month-old project, while open-ended R&D and deep debugging run outside it even on a 3-week-old one. Project maturity is the wrong variable; whether the end state is writable is the right one.

## Step 1 — One block per goal, and one refusal

**Take every goal the user handed over, not the most tractable one.** A person who walks away usually leaves a list. Write one block per item, numbered. `[范围]` is written once for the whole run.

```
[范围] {the surface this may touch, and what happens when the fix turns out to be outside it}

[目标 1] {what is true for the user when this is done — named cases, not a total}
[判据 1] {the command that proves it — runnable right now, printing per-case results}
[分辨力 1] {prior readings for this judge from .claude/afk/logs/, plus this session's two: A / B}

[目标 2] ... [判据 2] ... [分辨力 2] ...
```

⛔ **Do not silently drop a goal, and do not silently pick one.** Every item the user named gets a block or an explicit line saying why it cannot have one (no runnable judge — the refusal below). Dropping one is the failure this step was rewritten to stop. *(On record: two `/afk` runs on 2026-09-02 and 2026-09-04 each emitted a `/goal` line naming a single test class, while the session had been handed several items.)*

  - 来源：session_01DwyVvnaG3UTbmfy25nFstk 用户原话「它会抽取其中一个goal，然后让我粘，我也照做了，但这个goal只是我让它AFK的其中之一；感觉根本不是我想要的结果，敲了这个skill，我还是得把N选一的rules再粘一次让它做」

⚠️ **N blocks still produce exactly one `/goal` line.** [`/goal`](https://code.claude.com/docs/en/goal) holds **one goal per session** and *"if a goal is already active, the new one replaces it"* — handing the user N lines to paste would silently destroy all but the last. Step 3 composes the N end states and the N judge commands into a single condition (the cap is 4,000 characters).

**Each `[判据]` runs twice before anything else — not once.** Same command, no edit in between, both readings written down. One reading cannot tell a judge apart from a coin.

| Two readings | What it means |
|---|---|
| Both red | Start. The gap between them is the judge's own noise, and every threshold has to clear it |
| Both green | Stop — either the goal is already met or the judge tests nothing. Say which |
| One red, one green | ⛔ The judge is a measurement, not a function of the code. Its noise already spans the line you were about to draw. Do not start until the threshold sits outside that gap — and do not read the green one as "already met" or the red one as "ready to go" |

*(On record: `fix >= 24` was legislated off a "waterline" of 21 that was three samples wide. Nine later rounds read 16–23; the threshold it produced had P=0.109% per round and 0.00012% for the two consecutive rounds it demanded. Structurally red, and half a day spent against it. A second read at setup — which was already sitting there, 16 then 18 — would have shown it.)*

- **Two readings estimate noise badly — read the history before running anything.** If `.claude/afk/logs/` already holds readings for this judge, those are free samples and a better estimate than today can produce on its own; this session's two calibrate against them rather than standing in for them. ⛔ **Name the files the prior was drawn from, right there in `[分辨力]`.** One directory holds every arm of every judge, and a filename does not always say which judge wrote it — pooling two different metrics into one spread produces a number that cannot tell them apart, which is the failure this whole step exists to stop. Cannot tell which readings belong to this judge → they are not a prior, and today's two stand alone. *(On record: a judge's own comment put its spread at ±2, estimated off three samples. Nine later rounds spanned 16–22 — three times that — and the threshold that cost half a day was drawn against the small number. Each fresh reading also costs real device time: 210s to 426s per round on the recorded runs, so re-deriving what is already on disk is paid for twice.)*
- **A threshold carries a mechanism line, or it is not a threshold.** Beside it, name the specific case or defect each point of headroom comes from. "Current level plus twice the noise" is extrapolation wearing arithmetic. Cannot name them → the number is unspendable, and an unspendable number is indistinguishable from a broken judge; say so and pick a target you can spend.
- **`[目标]` names cases, not a total.** "These four go from wrong to right and hold on a re-run" is judgeable at n=1. "The total clears N" needs the total's variance to be smaller than the effect, which on a stochastic backend it usually is not — and an aggregate that barely moves can be a real win and a real loss cancelling out. *(On record: two targeted cases went 6/9 → 0/3 and 4/9 → 0/3, a reproducible win, while the aggregate the goal was written against read 19.78 → 19.00 and showed nothing.)*
- **If a goal has no runnable judge, name that goal and say so now.** This is the only refusal `/afk` makes, and it has to happen while the user is still here. With several goals it is per-goal: the ones that have a judge still go into the condition, the ones that do not are reported by name so the user can decide — drop it, hand it a judge, or keep it for when they are back. ⛔ Silently leaving it out is not the same as refusing it. Refuse the whole run only when **no** goal has a judge.
- **`[范围]` is the blast radius**, and it goes into the goal condition as a constraint. The route is not known yet — that is the whole reason this skill was chosen over `write-plan` — so the real fix landing outside the scope is an ordinary outcome, not an anomaly. Pick the branch now, while the user is here: **stop at the boundary**, or **extend in place and log it in the same turn**. Unstated defaults to stop.
- **Do not write a plan file, and do not invoke `write-plan`.** Nesting it would just relocate the precondition this skill exists to drop. If mid-run the work turns out to need a plan, stop and say so — a clean terminal.

## Step 2 — Clear what only a human can clear

**First: does this run need a physical device at all?** No — non-Apple repo, no device work — skip this step entirely.

If it does, in this order:

1. **Auto-lock off.** An idle device locks itself and `xcodebuild test` dies on `Unlock iPhone to Continue` → `code 74`. AFK *causes* this: the user walking away is the trigger. A probe cannot cover it — passing now says nothing about two hours from now, which is why this is first and why it is a request to the user rather than a check.
2. **Wired, not `localNetwork`.** What matters is where the CoreDevice tunnel was *established*. On a China-region iPhone, a tunnel established over Wi-Fi fails every UI test with `code 74`: the per-app "Wireless Data" setting denies Wi-Fi to all UITests-Runners, and the runner's traffic in a Wi-Fi-born tunnel counts as Wi-Fi. Unit tests are unaffected. A tunnel established while wired keeps working after the cable is unplugged.
   - So plug in before the run, and ⛔ never restart CoreDeviceService / remoted while unplugged, since that rebuilds the tunnel on Wi-Fi.
   - Evidence: `~/.claude/knowledge/platform-constraints/2026-09-26-iphone-xctest-code-74-wireless-data-shared-runner-uuid.md`.
3. **One minimal real-device UI test as a probe**, to force out whatever on-device trust/automation dialog exists right now. Probe, do not consult a list of known dialogs — a list goes stale, a probe surfaces today's.
4. ⛔ **Never reinstall the xctrunner as a remedy.** That reinstall re-triggers the very dialog it is meant to fix, and the loop is invisible from inside the run.

**Probe not constructable** (no UI test target, no paired device): say so now and **continue without device coverage**. Do not refuse to start, and do not create a UI test target to satisfy the probe — that scope is not yours to take.

Also name any other human-required unblock this run will touch: a `sudo` password, a simulator boot (which needs explicit approval), a credential near expiry.

## Step 3 — Hand over the `/goal` line

Present **every** block, **both** readings of **each** judge, the pre-flight outcome, any goal you could not hand a judge, and **every open question in one batch** — this is the last moment the user is reliably present.

Then give the line to paste. **One line, however many goals.** Build the condition from the three things `/goal` asks for, each of which now takes a list:

- **measurable end states** — from every `[目标 N]`, each named separately so the evaluator can tell them apart. Do not merge them into one aggregate sentence; an aggregate hides a goal that silently stopped moving.
- **stated checks** — from every `[判据 N]`, naming each command whose output the evaluator will read
- **constraints that matter** — from `[范围]`, **plus every constraint the user stated in this session**

⛔ **Sweep the session for the user's own constraints and put them in the condition.** Anything they said out loud during setup — 「不 push」「只用 iPhone」「不动那 60 条样本」「先做完 A 再动 B」 — lives only in the chat until it is written into the condition, and the chat does not survive compaction. Leaving it out is what forces the user to paste their rules a second time. *(On record — 用户原话，出处见 Step 1：「我还是得把N选一的rules再粘一次让它做」.)*

**Budget**: the condition caps at 4,000 characters. Over it → drop the least load-bearing constraints first, never a goal or a judge command, and say which ones you dropped.

```
粘这行然后走（一次会话只能挂一个 goal，粘第二行会顶掉第一行）：
/goal 同时满足：(1) {终态 1}；(2) {终态 2}；(3) …；
证据分别是 {命令 1} / {命令 2} / … 的原始输出，逐条贴全，不接受摘要；
{用户本轮说过的约束，逐条抄进来}；不改 {范围} 之外的文件；
或本轮回复里逐字给出 `## 终止：{原因}` 一节并贴出该轮原始输出（同一份内容同时写进 `.claude/afk/{slug}.md`）
```

⚠️ **`同时满足` is load-bearing.** The evaluator returns one verdict for the whole condition; without it, a condition listing several end states can be read as satisfied by any one of them.

⚠️ **The evaluator reads the transcript; it does not run commands or read files.** So the condition must be something Claude's own output can demonstrate, and the run must actually put that output in the transcript — which is what the done-gate below is for.

**That second branch above is an artifact — never an intention.** The work can turn out to be unreachable, and the run cannot release the hook itself, so the way out has to be something the evaluator can read verbatim. ⚠️ It reads the **transcript**, not files — so the branch is met by *emitting* that section in the turn; writing it to the run log is the durability half, and on its own it satisfies nothing. ⛔ **Not `或跑满 N 轮就停`.** A turn count is a state of mind and the evaluator judges text. *(On record: a run proved its goal mathematically unreachable, invoked exactly that clause, and was refused — "stopped after proving primary goal mathematically unreachable, not by deliberate procedural choice to halt at the 12-round boundary". Nine refusals followed in 2m13s; the run emitted `/goal clear` twice as plain text, then wrote 「我打不出斜杠命令——那一行是文本，不是执行」, and the user had to return and clear it by hand.)*

Tell the user three things they may not know: `/goal` only runs unattended in **auto mode** (otherwise it still asks before unapproved tool calls); it survives `--continue` / `--resume`; and **only they can `/goal clear` it** — the model cannot type a slash command, so a goal that cannot be met keeps re-entering the run until a human clears it.

## During the run

Route is yours — tools, order, whether to use agents, when to refactor. These are the whole constraint.

**Two gates. Both are here because the failure is on record, not because of any belief about what models can or cannot do.**

- **A done-claim carries freshly-run output, or it is not a done-claim.** Before reporting the goal met, re-run **every** `[判据 N]` in the condition and paste each one's raw output. Not the remembered result, not a summary — the output, from a run that just happened. ⛔ With several goals, one green judge is not a done-claim; the evaluator is judging `同时满足`, and a turn that shows only the judge that passed is how a multi-goal run gets signed off on a third of its work. This is also what feeds the evaluator: it can only judge what is in the transcript, so a summary of a passing test is exactly the input a false success needs. *(On record: a run reported completion in the same message that admitted 35 of 50 test suites were failing, using "not introduced this session" as the reason not to fix them.)*

- **No prose hand-back once you have a view.** About to end a turn with 「两件事要你拍板」/「你决定」/「从哪个开始？」 while you already have an opinion? That is not a decision point, it is outsourcing a judgment you have made. Take it, say what you took and on what evidence, mark what the user can overturn. This applies to plain text, not just `AskUserQuestion` — the structured tool has never been the leak; 16 deep-read invocations were all legitimate must-ask cases. *(On record: `我倾向做，但这个风险归你判断`.)*

  ⚠️ **Before any stop, check the candidates.** If the options you are about to hand over all circle one obstacle, or all rest on a premise nobody verified ("these two can't be done in the same pass", "A must precede B"), that is not a choice — it is a report that the work is a layer too low. Falsify the premise; the choice usually disappears. This qualifies a *question*. It is never a licence to work around a *failure*.

**Stop and end the turn for these** — `/goal` will re-evaluate on the user's return, so a stop is not the end of the goal:

| Situation | Why |
|---|---|
| The work would touch something outside `[范围]`, and Step 1 picked **stop** | Past that line there is no authorization. If Step 1 picked extend-in-place, log the extension in the turn it happens and keep going — that is not a stop, and it goes in the final report |
| An irreversible or outward-facing action | Deleting data, migrating, publishing, changing a shipped interface |
| A difference only the user can judge | A default, wording, an interaction shape, a layout, where technical fact picks no winner. ⛔ "Option A is faster so the experience is better" is **not** this — that is a technical fact; rank it yourself |
| The instruction admits ≥2 readings | Guessing costs a rebuild; asking costs a sentence |
| The work turns out to need a plan | Say so and stop; route to `write-plan` |
| **Any one** `[判据 N]` red twice **across a change meant to move it** — red before the edit, red after | One re-run separates a flake; a second red on a changed tree needs diagnosis, which needs the user. This is per-judge: one goal stuck stops the turn even while the others are still moving — carry on with them and it is the stuck one that silently drops out. ⛔ Re-reading an **unchanged** tree is not this — repeat reads with nothing changed are how `[分辨力 N]` gets measured, and treating them as a stop is what leaves a noisy judge unmeasured |

**If none of these fires, keep going.** "This is a good place to hand off" is not a terminal — it is a self-assessment, unfalsifiable and always available.

**Every stop writes the handoff first**: invoke `dev-workflow:handoff`, then end the turn. Handoff docs are the one artifact class that reliably gets read again, which is why the transfer goes there.

**Log every self-made decision** to `.claude/afk/<slug>.md` in the turn it happens — a batched write at the end loses the log to a context reset. Anything decided, deferred, or worked around goes in it and in the final report. A silent auto-decision is what makes a finished run untrustworthy.

**No review-report files.** Findings go in the final report, where they are read. *(Measured: review report files are written ~6× more often than they are read back; the findings that reached a human did so through the returning agent's text, not the file.)*

**When the goal is met, review before you sign off.** Invoke `dev-workflow:review-execution` with `scope_files` (what this run touched) and `mode: advisory`, then hand the findings to `dev-workflow:handoff` along with everything else. If the return's `status.ok` is not `true`, the handoff says the review **failed** and lists every `status.errored` entry — it is not reported as a clean review. No `plan_path` — an `/afk` run has no plan, so the plan-vs-code lens is skipped and the rest still apply.

This is the moment a fresh-context review is worth most: nobody watched any of the work happen. The user's own note on the one measured instance reads 「两次都是派出去的审查 agent 抓到的，我自己跑测试全绿、一点感觉都没有」 — findings that a passing test suite did not show.

⛔ **The findings must land in the handoff doc, not only on screen.** The user was away, so an on-screen summary reaches nobody; and by the time they return, Claude Code's prompt cache has expired, which makes resuming the old session *more* expensive than a cold start from the doc. Presenting and not writing is the failure mode here.

(The dependency question that held this back is answered: `review-execution` declares and is in fact standalone — it needs no plan and no dev-guide. It was never chain-bound; `implementation-reviewer` is the chain-bound one, and it is simply skipped here.)

## Dev-guide mode

Dev-guide mode is afk's second entry point: an **AFK autonomous driver** for an already-verified, already-planned multi-phase dev-guide. It drives every remaining phase to green without a timer, without scheduling, and without the user at the keyboard — auto-resolving low-severity decisions to their recommended option and honoring every severity gate. While it runs it is the **governing context**: when it reuses lower-level machinery (`run-phase`'s `phase.py` sequence, `verify-plan`, `execute-plan`, `test-changes`, `review-execution`), the Stop Policy below takes precedence over that machinery's own pacing and prompting behavior — pacing pauses are suppressed, severity gates are not.

Under `/goal`, "end the turn" alone does not end a run — the evaluator re-enters on the user's return. So every dev-guide-mode stop also emits `## 终止` (see "Every stop after the goal is armed" below), which releases the goal and leaves nothing pending. See `DESIGN-dev-guide-mode.md` for why this holds cold and hot alike.

**When:** `phase.py guide` resolves a dev-guide, and `phase.py locate` shows incomplete phases. **Resuming a stopped run is the same entry:** the user types `/afk` again. `/afk` is `disable-model-invocation`, so only a typed command loads it — a pasted `/goal` condition on its own never loads this section's Stop Policy or per-phase sequence. Setup item 1 finds the existing state and resumes it.

Every script below is invoked by its full path under `${CLAUDE_PLUGIN_ROOT}`, the convention `run-phase` uses. `guide.py` resolves every relative path against `--root` (default: the current directory, i.e. the project root), never against where it was launched from.

### Which goal-mode sections apply here

The rest of this file's goal-mode sections are written for a goal with no route. Some still apply as-is; some are overridden. This list is the single place that says which — do not infer it from reading both sections side by side.

- **Step 1 — One block per goal, and one refusal** does not apply. The judge is `phase.py locate`, the blocks are the dev-guide's remaining phases, and Step 1's "do not write a plan file, and do not invoke `write-plan`" rule is overridden: dev-guide mode writes each phase's plan itself, as part of the per-phase loop below.
- **Step 2 — Clear what only a human can clear** applies unchanged. This is new for dev-guide runs, which had no device pre-flight before.
- **Step 3 — Hand over the `/goal` line** is replaced by `guide.py goal-line` (see Setup item 5 below). The three notices it tells the user — auto mode only, survives `--continue`/`--resume`, only the user can `/goal clear` it — still apply and are still told to the user.
- **`## During the run`'s two gates** (a done-claim carries fresh output; no prose hand-back) apply. The done-claim re-runs `phase.py locate` and pastes the last phase's gated `review-execution` return object (its `rendered` field, not a hand-built summary), in place of re-running `[判据 N]`.
- **The goal-mode Stop table** is replaced by the dev-guide Stop Policy below. In particular, "the work turns out to need a plan → stop" does not apply — writing the phase's plan is this mode's normal work, not an escalation.
- **"Every stop writes the handoff first" and "log every self-made decision"** apply, with the stop order given under "Every stop after the goal is armed" below.
- **"No review-report files"** applies, and is why findings go into the handoff doc and run log rather than a final HTML report.
- **The goal-met advisory review** (`mode: advisory`, no `plan_path`) is replaced. Each phase already gets a `mode: gated` review with `plan_path` (Per phase, item 6). At goal-met, no extra advisory pass runs — the last phase's gated review is the final review, and `goal-line`'s judge condition (2) already requires it to show zero must-fix. `[选]` no extra pass; `[据]` goal-line condition (2) already requires that review to show zero must-fix; `[可推翻]` add an advisory pass over the whole run's `scope_files`.

### Setup (the user is present)

The user is present for every item here — on a first run because they just asked, and on a resume because they typed `/afk`.

1. **Target and branch.** `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py guide` resolves the dev-guide P (`ok:false` with `candidates` → ask which). Then `python3 ${CLAUDE_PLUGIN_ROOT}/skills/afk/scripts/guide.py resume-point --dev-guide P` names the branch:
   - **`state-error`** → the state file is unusable; follow run-phase Step 1 item 1's `ok:false` branches as written there (not restated here), then re-run `resume-point`. `migrate_first: true` → run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py migrate` first, per the same item.
   - **`all-complete`** → nothing to drive: the "No target resolved" setup-time terminal below.
   - **`init`** → `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py init --phase N --name … --dev-guide P --project …` for `locate_phase`.
   - **`resume`** → state exists, is not `done`/`finalized`, and is on `locate`'s phase. No `init`. The per-phase sequence below enters at `resume-point`'s `enter_at` — `state.phase_step`, except `pre-execute-gate` when the phase sits at `verify` and verify-plan already ran (re-dispatching it would break verify-plan's one-round rule, and a fresh verifier would re-raise the DP the user just answered in the report). `verify_report` is that phase's verify-plan report, read back from `state.verification_report`; pass it as `--verify-report` wherever a step below needs it. This is the normal branch when the user types `/afk` after a stop.
   - **`check-off`** → state says `done` but the dev-guide still shows that phase unfinished: the last run crashed between `phase.py step done` and `phase.py check-off`. Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py check-off --dev-guide P --phase N`, log it, and re-run `resume-point` (it now says `init` for the next phase, or `all-complete`). ⛔ Never `init` on this branch — `init` wipes `plan_file` and `task_progress`, and the finished phase would be driven again from scratch.
   - **`phase-mismatch`** → state exists and is not done, but on a different phase than `locate`'s. Show both phases in the authorization text (item 3) and let the user pick which to drive. Never run `init --force` on your own — it wipes `plan_file` and `task_progress`.
     - user picks the state's phase → resume at `state.phase_step`, and pass `state.plan_file` to `guide.py sweep-dps` via `--plans` (the `--dev-guide` source skips it, because `current_phase` ≠ `locate`'s phase).
     - user picks `locate`'s phase → the question itself must say `init --force` will wipe the other phase's `plan_file` and `task_progress`; run it only on that explicit answer.

   **Slug.** A new run picks a short kebab-case slug S for `.claude/afk/<slug>.*`. A resume reuses the one in `resume-point`'s `slugs` (the run that already has a goal file); several → ask which. **Empty `slugs` on a resume** (a legacy self-pacing run, or state left by `run-phase`) → pick a new slug, do **not** pass `--reuse-constraints` at item 5 (there is nothing stored; it exits 3), and collect the constraints from the user, who is present.
2. **Sweep and answer.** `python3 ${CLAUDE_PLUGIN_ROOT}/skills/afk/scripts/guide.py sweep-dps --dev-guide P [--plans …] [--verify-report R …]`, with any plan the user names and, on a resume, `resume-point`'s `verify_report` (the current phase's verify-plan report). Exit 3 with a non-empty `missing` means a named file is not there — fix the path; ⛔ never read a missing file as "zero open DPs". Ask every open blocking DP surfaced in one `AskUserQuestion` batch — on a resume this is where the DP the run stopped on gets answered. Record each answer with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/afk/scripts/guide.py adopt-dp --file <dp.file> --dp <dp.id> --label <A|B|…>` (the sweep's `file` field: the plan or the verify report the DP lives in). Invoke `dev-workflow:crystallize` only when at least one was answered, then `python3 ${CLAUDE_PLUGIN_ROOT}/skills/afk/scripts/guide.py crystal --slug S --path <the crystal file it wrote>` so the stop card points at that crystal and not at whichever crystal happens to be newest. Tell the user in the authorization text that later phases' decisions (their plans do not exist yet) surface in-loop instead. **If the card's last stop was "Awaiting visual sign-off"**, take the user's answer here too: log it to the run log; "looks right" → continue; a correction → apply it inside the plan's declared `**Files:**` before item 5, and log what changed.
3. **Authorization text** — names the dev-guide, `locate`'s starting phase **with its `checked/total` acceptance-criteria counts** (`resume-point`'s `locate_phase`), the number of remaining phases (`remaining_phases`), the full Stop Policy list below, and "every stop releases the goal; you resume by typing `/afk`, which hands you a fresh `/goal` line to paste." Only an explicit yes proceeds — on a resume too (autonomous mode is opt-in every time).
4. **Device unblocks** — run `## Step 2 — Clear what only a human can clear` here, unchanged. On a resume, re-check auto-lock at least: the device has had the whole away-time to change.
5. **Goal line.** `python3 ${CLAUDE_PLUGIN_ROOT}/skills/afk/scripts/guide.py goal-line --dev-guide P --slug S --constraint … --constraint …`, with every constraint the user stated this session, passed **most → least load-bearing**: over the 4,000-character condition cap, `goal-line` drops constraints from the end, and its `dropped` list names them — tell the user each dropped one by name. The line starts with `/goal `; present it verbatim together with the three notices from `## Step 3`. On a resume, add `--reuse-constraints`: the stored constraints from the first setup come first, then any new ones — on a cold resume there is no chat to re-collect them from. Always hand back this fresh line, never the card's old one: it carries the current plugin-cache paths, and a versioned cache path from before an update no longer exists.

### Per phase — the `phase.py` sequence

Copied from `run-phase`'s Step 1–8, in the order run-phase uses. "Resume at `state.phase_step`" (Setup item 1) enters this list at the matching step instead of starting at item 1.

1. **plan** — `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step plan` (a no-op right after `init`). Write the phase's plan with the Plan Writing Reference in `${CLAUDE_PLUGIN_ROOT}/skills/write-plan/SKILL.md`, skipping run-phase's scope-confirmation pause (the Setup authorization already covers it), then `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py set plan_file=<path>`. From this point on, the card's `plan` pointer comes from `state.plan_file`.
2. **verify** — `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step verify`, then `dev-workflow:verify-plan`. Its return carries `Report: <path>` — the `--verify-report` for items 3, 6 and 7 (recorded in state below, so a resume reads it back through `resume-point`). verify-plan writes its decision points into that **report**, not into the plan.
   - ⛔ **verify-plan's interactive DP step (its Step 3 item 5) is not asked mid-run.** Nobody is there to answer it. Every DP it wrote goes through item 3 instead: a `blocking` one takes the Critical-decision STOP row, a `recommended` one is adopted and logged.
   - `approved` → verify-plan Step 4 appends `- **Verdict:** Approved` to the plan.
   - `must-revise` → the Plan-fails-verification row: apply the revision items to the plan text only, log them, then append `- **Verdict:** Revised` with the items addressed to the plan's `## Verification` section (verify-plan's own completion-criteria form). Re-verify once only after a structural change. Without that line, item 3's gate reads the plan as unverified and stops — which would turn every `must-revise` back into a stop (`DESIGN-dev-guide-mode.md` invariant 4(a)).
   - Then `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py set verification_report="<verdict> — <Report path>"` — exactly that shape (`resume-point` parses the path after ` — `), and log the same line to the run log.
3. **Pre-execute gate** — `python3 ${CLAUDE_PLUGIN_ROOT}/skills/afk/scripts/guide.py unit-signals --plan <plan_file> --verify-report <Report path>`. Its `stop_rows` is the mechanical part of the Stop Policy — act on it, do not re-derive it by hand:
   - `blocking-dp` → the Critical-decision STOP row, batched with every other open item per the "ask everything at once" Hard Rule.
   - `verify-missing` (no verdict, or `partial`) → STOP (Plan fails verification row, loop exhausted). Verification is mandatory: the run will not pause per segment for human review, so plan quality matters more, not less, and an unverified plan never executes.
   - `author-checkpoint` → **not now.** It lists the marked tasks; it fires at the segment boundary after their batch completes (item 4).
   - every open `recommended` DP in `open_dps.dps` → `python3 ${CLAUDE_PLUGIN_ROOT}/skills/afk/scripts/guide.py adopt-dp --file <dp.file> --dp <dp.id>`, which writes `**Chosen:**` back into that file, and log it. (Conservative default applies: a DP whose severity looks wrong is treated as `blocking`.)
   - **Every non-trivial task has an executable verify line** (`**Verify:**` / `Automated verify`, or annotated `N/A — trivial`). A missing one is a plan-text defect, not a run failure — same class as `must-revise`: derive the line from the task's own `**Steps:**` and `**Files:**` (the command that would show the task worked), write it into the plan, and log the derivation. Only when nothing is derivable from the task as written does the "No derivable verify signal" terminal fire. Presentational/UI tasks (build + visual sign-off only) take the "Awaiting visual sign-off" path instead.
4. **execute** — `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step execute`, then `python3 ${CLAUDE_PLUGIN_ROOT}/skills/execute-plan/scripts/compute_checkpoints.py <plan_file> --k 3 --batch-size 5`, the `execute-plan` checkpoint init/resume, and the `${CLAUDE_PLUGIN_ROOT}/skills/execute-plan/execute-plan.workflow.js` segments it dispatches (this mode is a sanctioned Workflow trigger). Segment boundaries apply the Stop Policy below; a boundary whose batch contains a task from item 3's `author-checkpoint` row is the Author-declared-seam STOP.
5. **test** — `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step test`, then `dev-workflow:test-changes`, then `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py set test_report=<report path>`. The `visual` step is skipped (`test → review` is an allowed transition). UI tasks take the "Awaiting visual sign-off" cannot-proceed terminal instead, not the visual feedback loop.
6. **review** — `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step review`, then one `dev-workflow:review-execution` call with `plan_path`, `scope_files` (the plan's declared `**Files:**`), and `mode: gated`. ⛔ Gate on the return's `status.ok` first: `status.ok !== true` means the review **failed** (a reviewer threw or returned null, or nothing arrived) — take the Severe-failure STOP with every `status.errored` entry (`label`, `agentType`, `error`) in the card and the `## 终止` section, and do NOT write `review_reports` / `review_findings` (that sentinel is what lets `complete-gate` pass, so writing it would record a review that did not happen). Only on `status.ok === true`: N = `must_fix.length` and M = `nice_to_have.length` from the returned object, then `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py set 'review_reports=["review-execution:consolidated"]' 'review_findings={"must_fix": N, "nice_to_have": M}'`, then `python3 ${CLAUDE_PLUGIN_ROOT}/skills/afk/scripts/guide.py unit-signals --plan <plan_file> --verify-report <Report path> --must-fix N`. N > 0 → the In-scope must-fix row; **whether the repair stays inside the declared `**Files:**` (`unit-signals`' `files`) is your call** — inside → item 7, outside → the Severe-failure STOP.
7. **fix** (only for an in-scope must-fix, one cycle) — `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step fix`, repair the finding, back to **test**, re-review, then `python3 ${CLAUDE_PLUGIN_ROOT}/skills/afk/scripts/guide.py unit-signals --plan <plan_file> --verify-report <Report path> --must-fix N --after-repair` with the re-review's count. A `must-fix-after-repair` row → the Severe-failure STOP. Then `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py set gaps_remaining=<count>`.
8. **Clean seam** — `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py complete-gate`. `ok:true` → `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py step done` → `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py check-off --dev-guide P --phase N` → log "crossed phase N seam" to the run log. Then, if `all_phases_complete` is true, this is the goal-met terminal (the "During the run" done-claim gate). Otherwise, `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py init` for the next phase `python3 ${CLAUDE_PLUGIN_ROOT}/skills/run-phase/scripts/phase.py locate --dev-guide P` names, and loop back to item 1. A `complete-gate` block (`ok:false`) is never overridden — no `--override` here — and takes the severe row of the Stop Policy.

### Stop Policy

No phase-mode column (this mode has none); the phase-boundary row is folded into Per-phase item 8. **Every STOP row below ends the turn by emitting `## 终止：{row}`** (see "Every stop after the goal is armed"): under `/goal` that section is the only thing on record that releases the goal, so a stop that only ends the turn gets re-entered by the evaluator while the user is away.

| Situation | Maps to existing tag | Action |
|---|---|---|
| Critical decision | an unresolved `blocking` DP (plan or verify report) — `unit-signals` `stop_rows: blocking-dp` | **STOP** — the question verbatim in the card's `Why` and in the `## 终止` section. No `AskUserQuestion` in the stop turn: the user answers after typing `/afk`, at Setup item 2. |
| First red on a check | a task's `Automated verify` fails after its steps, build/test/lint goes red, or a prior-green check regresses | **RE-RUN ONCE** — the byte-identical command, changing no files. Green on the second run → log `flake: <command>` to the run log and continue. Red again → the severe row below. |
| Severe failure | the same check red twice, a review must-fix whose fix would touch a file outside the plan's declared `**Files:**`, `stop_rows: must-fix-after-repair`, or a `review-execution` return with `status.ok !== true` (a failed review, never a clean one) | **STOP** — card + `## 终止` carry the failing command and the relevant output from both runs. Do NOT invoke `fix-bug`, do NOT auto-fix. |
| In-scope must-fix | a must-fix repairable entirely inside the plan's declared `**Files:**` | **REPAIR ONCE** — apply the fix, re-run `test-changes`, re-dispatch the review. Clean → continue. Still must-fix (`must-fix-after-repair`), or the repair needs a file outside the declared set → STOP (severe row). |
| Plan fails verification | `verify-plan` returns `must-revise` | **CONTINUE** — apply the revision to the plan text only (never source files), append `Verdict: Revised`, and log it. Re-verify once only after a structural change. STOP only when a revision item needs a blocking decision (takes the blocking row above), a structural re-verify still returns `must-revise`, or `stop_rows: verify-missing` fires at the pre-execute gate. |
| Low-severity decision | a `recommended` DP | **CONTINUE** — `guide.py adopt-dp` writes its `**Chosen:**`; log it. |
| Low-severity finding | a `nice-to-have` review item | **CONTINUE** — defer to the run log. |
| Routine pacing pause | a `compute_checkpoints.py` hard-stop from batch 0 or a green dependency-hub batch | **CONTINUE** — auto-advance to the next segment. |
| Author-declared seam | an explicit `<!-- checkpoint -->` marker in the plan body (`stop_rows: author-checkpoint`), at the segment boundary after its task | **STOP** — the author placed it deliberately; skipping it is a forbidden silent downgrade. Resume: the user types `/afk`. |
| Clean phase seam | Per-phase item 8, `complete-gate` `ok:true` and no open must-fix | **CONTINUE** — cross the seam, log it, and loop to the next phase (Per-phase item 8). |

**Notes:**
- `must-revise` is not a severe failure — see `DESIGN-dev-guide-mode.md` invariant 4(a). Revising plan text is bounded, alters no product behavior, and any item that genuinely needs the user surfaces as its own `blocking` DP.
- **Conservative default — scoped, and scoped by reversibility.** If a decision's severity is ambiguous, or a finding could plausibly be critical, treat it as `blocking` and STOP. This governs only *how severe an already-occurring failure or decision is*; it never answers "should I keep working" — that question has no doubt-default, only the enumerated rows (`DESIGN-dev-guide-mode.md` invariant 4(b)). Where severity itself is genuinely ambiguous, resolve it on **reversibility, not confidence**: ambiguity about something that would mutate source files or ship user-visible behavior → stop; ambiguity confined to plan text, process ordering, or two equivalent approaches → continue and log. Confidence is unfalsifiable; reversibility is checkable.
- Every STOP row above, and every cannot-proceed terminal below, fires after the goal is armed and writes or refreshes the stop card before the turn ends. Do not skip it, and do not batch two stops into one card. Setup-time terminals (further below) write none.
- Every auto-decision — an adopted `recommended` DP, a deferred `nice-to-have`, an auto-crossed seam — must land in the run log. A silent auto-decision is what makes a finished run untrustworthy.

### Cannot-proceed terminals

These are not severity gates — the run physically cannot continue without a human, so there is nothing to weigh. **The distinguishing test is reversibility, not confidence:** a cannot-proceed terminal is one where no amount of additional model effort produces the missing input — a human preference, a human eye, an authorization. "A process document told me to stop" is not one of these; that is a rule conflict, resolved by the precedence order, not a block.

| Terminal | Fires when | Card variant |
|---|---|---|
| No derivable verify signal | a non-trivial task in the phase's own plan has no `Automated verify`, and one cannot be derived from the task's own `**Steps:**`/`**Files:**` (Per-phase item 3) | the task id + why no signal is derivable; `Next action` = revise that task in the plan |
| Awaiting visual sign-off | a presentational/UI task reached build-clean and its screenshot needs human eyes | screenshot path (in the run log and the handoff doc, not an HTML report) + what to confirm; `Next action` = "looks right" or the correction, given after typing `/afk` |

### Setup-time terminals

Before `guide.py goal-line` has run, the user is present and no goal is armed — tell them directly. No card and no `## 终止` are needed; `guide.py card` refuses without a goal file, which is correct at this point in the flow.

| Terminal | Fires when | Tell the user |
|---|---|---|
| No target resolved | no dev-guide exists, `resume-point` says `all-complete`, or the user declined at Setup item 3 | "no target resolved — {which branch}"; no dev-guide → `write-dev-guide`. There is no phase-mode fallback here. |

### Every stop after the goal is armed

Every STOP row above, and every cannot-proceed terminal, follows this order:

1. Write the stop to the run log (`.claude/afk/<slug>.md`).
2. Invoke `dev-workflow:handoff` (main session).
3. `python3 ${CLAUDE_PLUGIN_ROOT}/skills/afk/scripts/guide.py card --slug S --stopped-at … --why … --next … --doc <handoff path>` — doc first, so the card can name it. The card's `Resume with` tells the user to type `/afk` and quotes the last goal line for reference.
4. End the turn with the `## 终止：{row}` section, verbatim, plus that turn's raw output. This is what releases `/goal`. The same text is already in the run log from item 1.

### Hard rules kept

Carried over from self-pacing's Hard Rules (its last version before the merge, `git show 55c52da:dev-workflow/skills/self-pacing/SKILL.md`), adapted to dev-guide mode:

- Autonomous mode is opt-in, every time (Setup item 3 names the phase count explicitly, on a resume too). Never enter by inference.
- Severity gates are never suppressed — only pacing pauses are. A `blocking` DP and an explicit `<!-- checkpoint -->` stop when they fire. The three bounded-loop gates (`must-revise`, a red check, a `must-fix`) stop only after their one-cycle loop is exhausted, and the exhausted loop is itself the gate.
- **Stopping is enumerated, not judged — there is no default stop.** The run ends at green or at a row of the Stop Policy / cannot-proceed tables, which *is* the concrete blocking point; the card's `Why` + `Next action` *is* where it blocked and what unblocks it. **If no row fires, continue.** "This is the best state reachable in this session" / "good enough for a handoff" is not a terminal and must never be written as one — it is self-assessment, unfalsifiable and always available. Inherited from the user-wide CLAUDE.md 禁止行为 →「把还在跑的验证写成「未完成 / 待办 / 下轮再看」交回用户」(run it 「跑到出结论（通过 / 失败 / 一个具体的阻塞点）」), which already outranks this file (`DESIGN-dev-guide-mode.md` invariant 4(b)–(c)).
- **Context occupancy is not a terminal, and not a reason to move to a new session** — not mid-run, and not at the Setup authorization. The model has no token counter; "this session feels long" is not a measurement (measured instances sat at 28% / 57% / 73% while described as full). Where the environment surfaces a measured occupancy figure, only that figure is admissible; where none reaches the run, the claim is unavailable and the run continues. Hitting the limit does not lose work — the harness clears old tool output and summarizes. (`DESIGN-dev-guide-mode.md` invariant 4(b), its observed instance.)
- Pass the four-gate check before every STOP that is a judgment call (a `blocking` DP, an ambiguous-severity classification — not the severe-failure row or any cannot-proceed terminal, which stop unconditionally): what problem is being solved, is stopping aimed at it, is there an obviously better option, and are the candidates N workarounds circling one obstacle. Gate 4 in particular: if every option on the table circles the same obstacle, the question is not "which one" — it is a report that the work sits one layer too low; falsify the shared premise before stopping.
- When you do ask, ask everything at once — Setup item 2's sweep plus any in-loop blocking DP or open question from the current phase, batched.
- **The one class that is always the user's, however reversible: a difference they can directly perceive** — a default, wording, an interaction shape, a layout — where technical fact does not resolve it to one answer. "Option A performs better, so the experience is better" is a technical fact, not this; rank it yourself.
- No invisible auto-decisions — everything resolved, deferred, or auto-crossed appears in the run log.
- Bounded retry, never blind retry — exactly the two loops in the Stop Policy table (RE-RUN ONCE, REPAIR ONCE), each capped at one cycle and fully logged. Dev-guide mode still never invokes `fix-bug` and never diagnoses.
- Every STOP writes the stop card; every stop after the goal is armed also writes the handoff doc and ends with `## 终止` (see above). A card that has grown a "what I delivered" section is a doc that was written into the wrong file.
- `run-log ≠ crystal`, never mixed — user decisions the Setup sweep resolved go to a crystal via `crystallize` (recorded with `guide.py crystal`); in-loop decisions are recorded as `**Chosen:**` in the plan or verify report only (`guide.py adopt-dp`); auto-actions go to the run log incrementally.
- No timer, no background scheduling. Every stop ends the turn and releases `/goal`; resume is the user typing `/afk`, hot or cold.

### State & resume

`phase.py status` + the card. Cold resume: read the card, then its `Next action` doc, then its `Pointers`, then **type `/afk`**. Setup item 1 (`guide.py resume-point`) finds the existing state and resumes at `state.phase_step` (or finishes an interrupted `check-off`); item 2 asks any DP the run stopped on, now that the user is there; item 5 regenerates the goal line with `--reuse-constraints`; the user pastes that fresh line. The card's quoted goal line is for reference only — pasting it alone re-arms a condition without loading this mode's Stop Policy or per-phase sequence, and its plugin-cache paths go stale on the next plugin update.

See `DESIGN-dev-guide-mode.md` for the invariants this mode inherits.

## Artifacts

| Artifact | Path | When |
|---|---|---|
| Run log | `.claude/afk/<slug>.md` | incrementally, every self-made decision |
| Raw judge readings | `.claude/afk/logs/<date>-<judge>-<arm>.log` | every judge run, one file per round |
| Handoff doc | `docs/06-plans/HANDOFF-YYYY-MM-DD-HHMM.md` (via `dev-workflow:handoff`) | at every stop |
| Stop card (dev-guide mode only) | `.claude/afk/<slug>-handoff.md` (via `guide.py card`) | at every dev-guide-mode stop |
| Goal file (dev-guide mode only) | `.claude/afk/<slug>-goal.txt` (via `guide.py goal-line`) | at Setup (first run and every resume), so `card` can quote the last line for reference |
| Constraints (dev-guide mode only) | `.claude/afk/<slug>-constraints.json` (via `guide.py goal-line`) | at Setup; a resume passes `--reuse-constraints` so the user's constraints survive a cold start |
| Crystal pointer (dev-guide mode only) | `.claude/afk/<slug>-crystal.txt` (via `guide.py crystal`) | after Setup item 2's `crystallize`; the card's `crystal` pointer reads it |

State and checkpoint are owned by `phase.py` (`.claude/dev-workflow-state.json`) and `execute-plan` (`.claude/execute-plan-checkpoint.json`), not by this skill.

⛔ **Readings do not go in the session scratchpad.** A run lost `arm-b1.log` / `arm-b3.log` that way and had to buy the rounds again on device. `.claude/` is gitignored — local only, but it survives the session, and these readings are the next run's `[分辨力]` prior, which is the whole reason they have to outlive the session that produced them.

The code plus these files are the source of truth. Chat is not — on a cold resume there is no chat.

## Relationship to the rest of the flow

- **`/goal`** (native) owns the loop and the completion judgment. This skill owns the setup and hands off to it.
- **`write-plan` → `verify-plan` → `execute-plan`** owns route-known work. Goal mode does not invoke that chain and does not replace it; the table above routes between them. Dev-guide mode is the exception: it drives that chain itself, once per phase (Per-phase items 1–4), because a verified dev-guide is route-known work that spans phase seams.
- **`/self-pacing`** is now a pointer to `/afk` dev-guide mode.
- **`fix-bug`** remains the diagnostic protocol for a reported defect. `/afk` does not invoke it and runs no formal diagnosis — though the layer question it enforces (what did the existing design solve; is this patch treating a symptom) is the same question the ⚠️ above asks before a stop.
- Nothing else is modified — except, in dev-guide mode, the dev-guide and state file (via `phase.py`), each phase's plan (written and revised by the run), and the `**Chosen:**` lines `guide.py adopt-dp` writes into plans and verify-plan reports.
