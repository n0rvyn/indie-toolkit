---
name: brainstorm
description: "Use before any creative work — creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation."
---

## Hard Gate

Do NOT invoke any implementation skill, write code, or take implementation action until design is presented and user-approved.

## Division of Responsibility

- **brainstorm** = from zero to design (exploring, shaping, deciding)
- **design-decision** = choosing between already-identified options

If the user already has 2+ concrete options and needs to pick one, use `dev-workflow:design-decision` instead.

## Process

### 1. Explore Project Context

**First, search the knowledge base (if search tool available):**
1. Extract 3-5 domain keywords from the user's request (component type, domain area, technology names)
2. Call `search(query="<domain keywords>", source_type=["doc", "error", "lesson"], project_root="<cwd>")`
3. If results are returned: note existing architecture decisions and lessons; use them to avoid proposing approaches already tried or decided against
4. If the search tool is unavailable or returns no results: skip silently

Then:
- Read relevant code, configs, and docs
- Understand what exists before proposing anything new

### 2. Ask Clarifying Questions

Ask **one question at a time**. Wait for the answer before asking the next.

Focus on:
- What problem are we solving?
- Who is the user? What do they care about?
- What constraints exist (tech stack, timeline, compatibility)?
- What does success look like?

### 3. Propose 2-3 Approaches

For each approach, provide:
- Summary (1-2 sentences)
- Key trade-offs
- When this approach is the right choice

Follow the comparison table format from CLAUDE.md Rule 13:

| Approach | Architecture Fit | Implementation Size | Risk/Cost | Best For |
|----------|-----------------|-------------------|-----------|----------|
| A | ... | ... | ... | ... |
| B | ... | ... | ... | ... |

Mark your recommendation and explain why in one sentence.

### 4. Present Design Incrementally

After the user picks a direction:
- Present design in sections of 200-300 words
- Get approval on each section before moving to the next
- Cover: data model, component structure, key interactions, edge cases

#### 4a. User Journeys & UX Assertions (user-facing designs only)

If the design involves user-visible behavior (UI components, interaction flows, navigation changes), add a final design section with two parts:

**Part 1: User Journeys**

Step-by-step narratives of what the user sees and does. One journey per primary flow. These give the plan-writer readable context to understand interaction intent.

```markdown
## User Journeys

### Journey: [Name]
1. User [action] → sees [result]
2. User [action] → [component] responds with [behavior]
3. ...
```

**Part 2: UX Assertions**

Structured, verifiable assertions. Each captures one specific behavioral expectation with a concrete verification method. These are checkpoints that the plan-verifier uses to validate plan faithfulness.

```markdown
## UX Assertions

| ID | Assertion | Verification |
|----|-----------|-------------|
| UX-001 | [Behavioral expectation in user's language] | [How to verify in code: Grep target, component check, state inspection] |
| UX-002 | ... | ... |
```

Rules:
- Assertions must be verifiable by reading code, not by running the app
- Reference observable behavior, not implementation details
- Verification column names specific files, components, or patterns to check
- Number assertions sequentially (UX-001, UX-002, ...) for cross-referencing in plans and verification

If the design has no user-visible behavior (pure infrastructure, data model only), skip this section.

### 5. Save Design Document

Write the approved design to:

```
docs/06-plans/YYYY-MM-DD-<topic>-design.md
```

If the design is primarily architectural (data model, service layer, component boundaries), also save or symlink to `docs/02-architecture/` so it's discoverable alongside other architecture docs.

### 6. Next Steps

After design is approved, inform the user:
- Use `dev-workflow:write-plan` to create a structured implementation plan

## Completion Criteria

- User has approved a design direction (Step 4 sections all confirmed)
- Design document saved to `docs/06-plans/` (Step 5 completed)
- Next step (write-plan) communicated
