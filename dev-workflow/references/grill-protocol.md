# Grill Protocol (reference)

A high-intensity clarifying-question mode used by `brainstorm` (and optionally `write-plan` when requirements feel under-specified) to align the AI and the user on a **design concept** before any asset (plan, code, doc) is generated.

Origin: Matt Pocock's "grill-me" skill (open-sourced as part of his Claude Code skills repo, ~13k stars at time of authoring). Adapted from Frederick P. Brooks' notion of the "design concept" — the invisible, ephemeral shared theory of what's being built, distinct from any markdown artifact.

## When to invoke

Trigger this protocol when **any** of these hold:

1. The task touches 2+ existing modules (high cross-impact, design tree has branches that depend on each other)
2. The requirements use abstract or evaluative words ("intuitive", "feels right", "better than current") without concrete observable criteria
3. The user has rejected 2+ prior framings of the same problem (signal: shared mental model not yet established)
4. The work will commit to a long-lived contract — public API shape, data model schema, design-system token — where a wrong call costs days to undo

Otherwise, stay with `brainstorm`'s default Step 2 Grill-Loop (recommended answers, one question at a time). This protocol is an escalation, not a default.

## When NOT to invoke

- The task is mechanical with clear specs (move file A to B, rename X to Y, add field Z to model)
- The user has explicitly locked the approach ("just use X, don't ask")
- A spec / design doc / crystal file already settles the question (read it first, then ask only what's genuinely open)
- The user is debugging / fix-bug mode (asking 40 questions about a stack trace is friction, not alignment — use `fix-bug`'s diagnostic flow instead)

## Protocol

### Step G1 — State the design tree

Before asking any question, write out the visible design tree:

```
[Design Tree]
Root: {what we're building, 1 sentence}
├── Branch A: {sub-decision area}
│   ├── A1: {decision point}
│   └── A2: {decision point}
├── Branch B: {sub-decision area}
│   └── B1: {decision point}
└── Branch C: {sub-decision area}
    ├── C1: depends on A2 — answer A2 first
    └── C2: {decision point}
```

The tree makes dependencies explicit. A decision in C1 depends on A2 means you cannot ask C1 productively before A2 is resolved.

### Step G2 — Walk the tree in dependency order

Ask one question at a time, in dependency order. For each:

```
Q: {direct question}
推荐答案: {best guess from context}
理由: {why this is the default, 1 sentence}
何处不对? (回答 "对" / 选另一个 / 指出哪个假设错了)
```

Rules:
- One question per turn — never batch
- Always state your recommended answer first; the user reviews, not generates
- If the user picks a non-recommended option, treat it as a **signal about an assumption you held**; surface the assumption explicitly before moving on:
  > "你选了 B 而不是推荐的 A。我之前假设了 {X} —— 这个假设错了吗？"
- Track resolved decisions in a running ledger so later branches can reference them

### Step G3 — Loop until convergence

Keep walking branches until:
- **Convergence signal**: the next question's answer is predictable to both sides ("at this point I'd just say Y, right?" — user confirms in one word)
- **Saturation signal**: 3+ questions in a row receive "对" on the recommended answer with no new information surfaced
- **User-called stop**: "够了" / "可以了" / "go" — but only after the design tree's blocking branches are resolved

The skill's job at this point is **NOT to declare done**; it is to summarize what's resolved and what's still open:

```
[Convergence Summary]
Resolved (N decisions):
- A1: {chosen}, because {reason}
- A2: {chosen}, because {reason}
- ...

Still open (M decisions — non-blocking for the design concept):
- B2: {will resolve at implementation time}
- C2: {depends on B2 outcome}

Design concept (what we both now see):
{2-4 sentences describing the shared mental model}

Proceed? (回复 "对齐了" 进入下一阶段; 或指出哪一行还不对)
```

Only the user's explicit "对齐了" / "yes proceed" exits the protocol.

### Step G4 — Hand off to the consuming skill

The consuming skill (typically `brainstorm` Step 3 onward, or `write-plan` Step 2) inherits:
- The design tree with resolved decisions marked
- The convergence summary's "design concept" paragraph (used verbatim in the design doc's overview)
- The list of still-open decisions (becomes the consuming skill's DP-xxx candidates)

## Intensity calibration

Matt Pocock's open-source skill is famous for asking 40–100 questions before satisfaction. That number is a function of stake, not a target.

| Stake | Typical question count | Stopping rule |
|-------|------------------------|---------------|
| Long-lived contract (public API, schema) | 20–60 | All blocking branches resolved |
| New feature, contained module | 10–20 | Core design concept agreed |
| Behavior tweak to existing feature | 3–8 | One axis of ambiguity removed |
| Bug investigation entry point | 1–3 | Stack trace + repro confirmed (then exit to fix-bug) |

Calibrate intensity to stake. A 50-question grill on a 10-line CSS tweak is friction; a 3-question grill on a database migration is malpractice.

## What this protocol is NOT

- **NOT a substitute for reading code.** Before asking any clarifying question, the AI must have read the relevant files. Asking "how does X currently work?" when the answer is in a file the AI hasn't opened is laziness disguised as alignment.
- **NOT a way to defer judgment.** If the AI has a strong recommendation based on code evidence, it must state it as the recommendation, not hide it behind a neutral question.
- **NOT a chat-mode entry point.** The protocol terminates with a design concept that consumes into another skill's flow. If there's no consuming skill (no plan to write, no design to capture), the protocol shouldn't have been invoked.

## Distinguishing from `brainstorm` Step 2 (default Grill-Loop)

`brainstorm`'s default Step 2 already does most of this — recommended-answer questions, one at a time, an Expectation Recap before proceeding. That default works for ~80% of brainstorms.

This protocol differs in two ways:

1. **Explicit design tree first** (G1). The default mode lets questions emerge ad-hoc; this protocol surfaces the dependency structure before asking anything.
2. **Higher convergence bar** (G3). The default mode advances after a brief recap; this protocol requires explicit "对齐了" after a Convergence Summary that enumerates resolved + still-open.

Use the default when the design is mostly clear and a few questions will settle it. Use this protocol when the design has structure that's not yet visible — branches, dependencies, contested assumptions.

## Source

Matt Pocock, "Software Fundamentals Matter More Than Ever" (talk, 2025). Original skill prompt was a single paragraph; this reference expands it to a callable protocol with named steps, integration hooks for `brainstorm` and `write-plan`, and stake-based intensity calibration.
