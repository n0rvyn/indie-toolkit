---
name: crystallize
description: "Use before /write-plan or when the session has settled significant design decisions. Extracts the decision history from the current conversation — initial ideas, discussion points, rejected alternatives, and final conclusions — into a persistent crystal file that plan-writer and plan-verifier consume."
user-invocable: true
---

## Overview

Extracts settled decisions from the current conversation into a persistent file (`docs/11-crystals/`). This bridges the gap between human-AI discussion and structured planning: the plan-writer agent runs in a separate context and cannot see the discussion history, so it needs an explicit record of what was decided and why.

## When to Use

- After a `brainstorm` or `design-decision` session that involved trade-offs, rejected alternatives, or changed assumptions
- Before `/write-plan` when the conversation contains decisions that the plan-writer agent must respect
- Before `/handoff` when decisions from this session need to survive into the next session
- Any time the user says "lock this", "crystallize", "record these decisions"

## Process

### Step 1: Decision Source Identification

Scan the current conversation context for decision signals.

**High-signal sources** (must process if present):
- `brainstorm` output — design document paths, UX Assertions, approach selections
- `design-decision` output — comparison tables with user's selection
- Explicit user decision statements — "用 X 方案", "不要 Y", "选 A", "go with", "let's do", "decided on"

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
- **{Alternative name}**: Rejected because — {specific reason}
- **{Alternative name}**: Rejected because — {specific reason}

## Decisions (machine-readable)
- [D-001] {clear conclusion in imperative form}
- [D-002] {clear conclusion}
- [D-003] {clear conclusion}

## Constraints
- {Constraints that emerged from the discussion}

## Source Context
- Design doc: {path or "none"}
- Design analysis: {path or "none"}
- Key files discussed: {path list}
```

**Extraction rules**:
- **Initial Idea is denoising, not summarizing**: preserve the user's original content and phrasing. Only clean noise (filler, repetition, tangents). AI must not rephrase — rephrasing introduces interpretation bias that gets permanently baked into the crystal.
- Each `[D-xxx]` must be decidable — a plan can be checked against it (does the plan comply or not?)
- Do not record pure implementation details (naming, variable splitting); only record decisions that affect deliverables and behavior
- Rejected Alternatives must include the reason for rejection, not just "rejected"
- Discussion Points must show the pivot (from X to Z), not just the final conclusion

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
- /write-plan — plan-writer reads it as context to avoid dropping settled decisions
- /verify-plan — plan-verifier checks plan tasks against each D-xxx decision

Proceed with /write-plan when ready.
```

## Completion Criteria

- Crystal file saved to `docs/11-crystals/`
- User has confirmed the extracted decisions
- Next step communicated
