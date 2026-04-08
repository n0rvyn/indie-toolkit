---
name: crystallize
description: "Use before /write-plan or when the session has settled significant design decisions. Extracts the decision history from the current conversation into a persistent crystal file that /write-plan and plan-verifier consume."
user-invocable: true
---

## Overview

Extracts settled decisions from the current conversation into a persistent file (`docs/11-crystals/`). This creates a structured, machine-readable record of what was decided and why, consumed by plan writing and verification steps.

## When to Use

- After a `brainstorm` or `design-decision` session that involved trade-offs, rejected alternatives, or changed assumptions
- Before `/write-plan` when the conversation contains decisions that the plan must respect
- Before `/handoff` when decisions from this session need to survive into the next session
- Any time the user says "lock this", "crystallize", "record these decisions"

## Process

### Step 1: Decision Source Identification

Scan the current conversation context for decision signals.

**High-signal sources** (must process if present):
- `brainstorm` output — design document paths, UX Assertions, approach selections
- `design-decision` output — comparison tables with user's selection
- Explicit user decision statements — "用 X 方案", "不要 Y", "选 A", "go with", "let's do", "decided on"
- Revert/rollback events — user requested revert of changes, with the categories of change that were reverted (e.g., "font changes", "layout restructure", "feature removal"). Each reverted category becomes a Constraint and an OUT scope boundary.

**Medium-signal sources** (extract but mark as inferred):
- AI proposals that the user modified ("originally proposed X → user changed to Y")
- Alternatives discussed but not adopted
- User-stated constraints ("必须兼容 Z", "不能用 W", "must support", "can't use")

Also search for source context to populate the `## Source Context` section:
- Design doc: search `docs/06-plans/*-design.md` for the most relevant file
- Design analysis: search `docs/06-plans/*-design-analysis.md` for the most relevant file

If no decision signals are found in the conversation, inform the user:

> No significant decisions detected in this session. Crystallization is not needed. If you believe decisions were made, describe them and I'll record them.

Exit without creating a file.

### Step 2: Structured Extraction

Extract from identified signals and assemble into the following structure:

```markdown
---
type: crystal
status: active
tags: [{topic keywords from Discussion Points}]
refs: [{design doc path, design analysis path from Source Context}]
---

# Decision Crystal: {topic}

Date: YYYY-MM-DD

## Initial Idea
{User's original statement with noise removed — preserve the original content and wording.
Only clean up: filler words, repetitions, off-topic tangents, speech-recognition typos.
Do NOT rewrite, do NOT summarize. If the user spoke in Chinese, keep Chinese.}

## Discussion Points
1. **{Point A}**: Initial assumption was {X}, discovered {Y} (code evidence / user feedback), decided {Z}
2. **{Point B}**: {same structure}

## Rejected Alternatives
- **{Alternative name}**: Rejected because — {specific reason}. Rejection scope: {what exactly was rejected}; does NOT reject {what remains valid}.
- **{Alternative name}**: Rejected because — {specific reason}. Rejection scope: {scope}.

## Decisions (machine-readable)
- [D-001] {clear conclusion in imperative form, traceable to user's words}
- [D-002] {clear conclusion} (linked: D-003 — {relationship description})
- [D-003] {clear conclusion}

### AI-supplemented
- [D-S01] ⚠️ AI 补充 {AI-inferred decision} — Reasoning: {why AI thinks this is needed}

## Constraints
- {Constraints that emerged from the discussion}

## Scope Boundaries
- IN: {item from user's explicit request — quote or paraphrase user's words}
- IN: {item}
- OUT: {item user explicitly excluded, or category that was reverted}
- OUT: {item}

## Source Context
- Design doc: {path or "none"}
- Design analysis: {path or "none"}
- Key files discussed: {path list}
```

**Extraction rules**:
- **Initial Idea is denoising, not summarizing**: preserve the user's original content and phrasing. Only clean noise (filler, repetition, tangents). AI must not rephrase — rephrasing introduces interpretation bias that gets permanently baked into the crystal.
- **Decision traceability**: Each `[D-xxx]` must be decidable (a plan can be checked against it) AND traceable to a specific user statement. For each D-xxx, the AI must be able to point to the user's words that led to it. If the AI cannot quote or closely paraphrase the user, it is an AI inference, not a user decision. AI-inferred decisions must be listed in a separate `### AI-supplemented` sub-section under Decisions, each prefixed with `⚠️ AI 补充` and the reasoning that led to the inference. The user confirms or rejects these separately.
- **Decision relationships**: When the user states that two decisions are linked, co-located, or conditionally dependent (e.g., "A and B should be in the same module", "if A is strict enough, B is unnecessary"), record the relationship inline: `[D-002] ... (linked: D-006 — permissionMode strictness determines whether Bash control is needed)`. Do not split linked decisions into independent items without preserving the linkage.
- Do not record pure implementation details (naming, variable splitting); only record decisions that affect deliverables and behavior
- **Rejected Alternative precision**: Rejected Alternatives must include both the **reason** for rejection AND the **scope boundary** of rejection. Format: `**{Alternative name}**: Rejected because — {reason}. Rejection scope: {what exactly was rejected}; does NOT reject {what remains valid or open}.` Example: "Method C hybrid (Application Gate + Bash Policy): Rejected because — over-designed. Rejection scope: the entire Method C design including readablePaths whitelist and bashPolicy enum; does NOT reject (a) Bash fine-grained management as a direction, (b) sandbox participating in read restriction." Record the rejected item at the actual granularity the user rejected — if the user rejected a whole approach, do not split it into component rejections; if the user rejected only a specific design within an approach, do not inflate to rejecting the approach.
- **Timeline awareness**: Discussion evolves. A discovery mid-conversation (e.g., finding an SDK feature) can invalidate earlier assumptions and reframe subsequent decisions. Discussion Points must reflect this evolution, not flatten everything into a single phase. When the discussion has a clear turning point, use phase headers (e.g., "Phase A: before X discovery", "Phase B: after X discovery") to show what changed and why. Rejected Alternatives must note which phase they belong to — an alternative rejected in Phase A may be rejected for different reasons than it would be in Phase B. Decisions made in Phase B should not be misattributed as modifications of Phase A proposals if they arose independently.
- **Discussion Point fidelity**: Discussion Points must show the pivot (from X to Z), not just the final conclusion. When the user provides concrete examples, routing rules, flow descriptions, or specific scenarios to illustrate a decision, preserve the essential detail in the Discussion Point — do not abstract "微信A triggers, report_to is A, deliver_to is B, approval goes to A" into "end-to-end verification needed."
- **Frontmatter fields:** `type` is always `crystal`. `status` is always `active`. `tags` — derive 2-4 keywords from the Discussion Points topics and Decisions content. `refs` — list the design doc and design analysis paths from Source Context (omit entries that are "none").
- **Scope Boundaries** distinguish user-authorized work from AI inference. IN items must trace to user's words (direct quote or close paraphrase). OUT items come from: explicit user exclusion ("不要改 X"), revert events (user reverted font changes → "OUT: font/typography changes"), or user-stated constraints. If the user did not explicitly authorize an item, it is NOT an IN item — do not infer scope from design docs or AI analysis. If the conversation produced no explicit scope signals (no user-stated items to include or exclude), omit the `## Scope Boundaries` section entirely.

### Step 3: User Confirmation

Present the extracted crystal to the user in markdown format. Ask:

1. Are any decisions missing?
2. Is anything recorded inaccurately?
3. Confirm to save?

The user can edit, add, or remove items. Apply their changes before saving.

### Step 4: Save

Write to `docs/11-crystals/YYYY-MM-DD-{topic}-crystal.md`.

If the `docs/11-crystals/` directory does not exist, create it.

`{topic}` source:
- If a brainstorm design document exists: extract from the design document filename (e.g., `feature-sync-design.md` → `feature-sync`)
- If no design document: infer a short topic keyword from the Discussion Points

If the target filename already exists, insert a sequence number before the `-crystal` suffix: `YYYY-MM-DD-{topic}-2-crystal.md`, `-3-crystal.md`, etc. This keeps the `-crystal.md` suffix intact for consumer glob patterns (`*-crystal.md`).

### Step 5: Next Steps

After saving, inform the user:

```
Crystal saved to docs/11-crystals/{filename}.

This crystal file will be automatically consumed by:
- /write-plan — plan-writer reads D-xxx decisions and scope boundaries to stay within authorized scope
- /verify-plan — plan-verifier checks plan tasks against each D-xxx decision AND scope boundaries (CF-3)

Optional: Run `/generate-bases-views --target crystals` to update the Obsidian Bases decision dashboard.

Proceed with /write-plan when ready.
```

## Completion Criteria

- Crystal file saved to `docs/11-crystals/`
- User has confirmed the extracted decisions
- Next step communicated
