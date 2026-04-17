---
name: brainstorm
description: "Use before any creative work — creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design through iterative one-question-at-a-time conversation before implementation. Not when: task is mechanical with clear specs (use write-plan) or the user has already locked the approach (just implement)."
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

#### 4b. Visual Design Decisions (user-facing designs only)

If the design involves user-visible UI (same trigger as 4a), confirm these visual decisions before saving the design document:

**Hierarchy Strategy**
- What is primary / secondary / tertiary information on each key page?
- Text hierarchy: how many size levels x color levels x weight levels? (Target: <=3 sizes from type scale, 2-3 foreground colors, 2 weights)
- Action hierarchy: which action is primary (solid), secondary (outline/tinted), tertiary (text-only)?

**Spacing & Density**
- Density profile per page type? (Compact / Standard / Comfortable — ref ui-design-principles.md S2.5)
- Use project's existing spacing scale or establish one?

**Color Scheme**
- Reuse existing palette or extend? Which semantic colors needed?
- Color ratio target for app type (tool: 80/15/5, content: 60/30/10)
- Dark mode strategy for new colors

Present as table for user confirmation:

| Page/Component | Info Hierarchy | Density | Key Color Decisions |
|----------------|---------------|---------|---------------------|
| {page name} | Primary: X, Secondary: Y, Tertiary: Z | Standard | Reuse existing palette |

User can skip rows — use project defaults or ui-design-principles.md reference values.
These decisions flow into the design document and constrain plan-writer output.

If the design has no user-visible behavior (pure infrastructure, data model only), skip this section.

### 5. Save Design Document

Write the approved design to:

```
docs/06-plans/YYYY-MM-DD-<topic>-design.md
```

The design document must begin with YAML frontmatter:

```yaml
---
type: design
status: active
tags: [tag1, tag2]
refs: []
---
```

`type` is always `design`. `tags` — derive 2-5 keywords from the design topic and major concepts discussed (e.g., a sync feature design → `[sync, conflict-resolution, offline]`). `refs` — list the project brief path and any architecture docs referenced during the brainstorm session. `status` starts as `active`.

If Step 4b (Visual Design Decisions) was completed, include a `## Visual Design Decisions` section in the design document with the confirmed hierarchy/density/color table.

If the design is primarily architectural (data model, service layer, component boundaries), also save or symlink to `docs/02-architecture/` so it's discoverable alongside other architecture docs.

### 6. Next Steps

After design is approved, inform the user based on the design type:

**If the design has UX Assertions (user-visible UI):**

> Design approved. Before writing the implementation plan, consider creating a visual prototype:
>
> 1. Use `/generate-design-prompt` to get a Stitch or Figma prompt based on this design
> 2. Create the prototype in your design tool
> 3. Use `/understand-design` to bring the prototype back for AI analysis
> 4. If issues found: use `/generate-design-prompt refine` to get improvement prompts, iterate
> 5. Then use `/write-plan` to create the implementation plan
>
> Or skip prototyping and go directly to `/write-plan`.

**If the design is infrastructure-only (no UX Assertions):**

> Design approved. Use `/write-plan` to create a structured implementation plan.

**If significant decisions were made during this brainstorm** (rejected alternatives, changed assumptions, architectural constraints):

> Consider running `/crystallize` to lock these decisions before proceeding to `/write-plan`. This ensures the plan-verifier agent — which runs in a separate context for unbiased review — knows what was discussed and decided.

## Completion Criteria

- User has approved a design direction (Step 4 sections all confirmed)
- Design document saved to `docs/06-plans/` (Step 5 completed)
- Next step communicated (prototype workflow or write-plan, based on whether design has UX Assertions)
