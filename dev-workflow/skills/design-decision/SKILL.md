---
name: design-decision
description: "Use when facing multiple design or product options, the user is stuck between approaches, or asks '选哪个', '怎么设计', 'how should I design this', 'which is better'. Analyzes trade-offs by separating essential from accidental complexity and presents a structured comparison. Not when: options are not yet identified — use brainstorm first to surface candidates."
---

## Input

Trigger this command when:
- User presents multiple options and asks which is better
- User is stuck between approaches
- User asks "how should I design this"

Required context:
- What problem are we solving?
- Who is the user?
- What are the constraints?

If any required context is missing, use `AskUserQuestion` with a single batch of 1–3 questions covering: (a) the options to compare, (b) constraints/deadlines, (c) tentative preference. Do not ask these one at a time — batching gets the full picture in one turn.

**Fallback**: if `AskUserQuestion` is not available in the current invocation context (e.g., skill invoked via hook or programmatic dispatch), ask in prose as a single consolidated message instead — do not split into sequential turns.

## Hard Gate: Verify Existing-Code Claims

When any option refers to behavior of existing code in this project (e.g., "Option A: extend the current Router pattern", "Option B: replace the current sync logic"), you MUST verify those claims by reading the cited files before recommending. Do not infer current behavior from naming, conversation history, or training data.

- **Required first action**: For each option that cites existing code, locate and read the referenced file/function. Cite `file:line` in the comparison table.
- **Forbidden**: "Based on typical patterns…", "this codebase probably…", or any claim about current behavior without a file citation.
- **Self-check**: Remove the recommendation line. Can a reader confirm each option's claim about existing code by following only your file citations? If not, the verification is insufficient.

The user's friction reports show speculative answers about codebase architecture are the #1 cause of repeated frustration; this gate exists to prevent that mode.

## Analysis Framework

### Step 0: Out-of-scope check

Before comparing options, list `dev-workflow/.out-of-scope/*.md` and read titles + `**Decision:**` lines. If any of the options to compare matches a rejected entry, surface this to the user: "Option {X} was previously rejected per .out-of-scope/{file} — keep in comparison or remove?" Default: remove unless user keeps explicitly.

### Step 0.5: Pre-decision Expectation Check

Before applying the essential-vs-accidental complexity framework, articulate your understanding of the user's situation in plain language (no jargon, no framework terms):

```
[Pre-decision Expectation Check]
你想达成的目标: {1-sentence outcome in user's words}
你的约束: {1-sentence constraint set — time, tech stack, team, audience}
你真正在意的是: {1-sentence underlying concern — often different from the surface preference}

这三条对吗? (回复 "对齐了" 进入选项分析;
或指出哪一条偏了)
```

You cannot run Step 1's complexity analysis until the user confirms the framing.

**Why this gate exists:** comparing options that solve the wrong problem produces a confidently-wrong recommendation. The 推荐 reason looks rigorous because it cites trade-offs, but the trade-off axes are themselves miscalibrated. This gate forces the AI to surface its framing assumption before the user spends attention on options.

### Step 1: Understand the Complexity Source

Before applying simplicity principles, determine:
- **Essential complexity**: Inherent to the problem domain (e.g., tax rules are complex because taxes are complex)
- **Accidental complexity**: Added by the solution (e.g., over-abstraction, premature optimization)

Only accidental complexity should be eliminated. Essential complexity must be managed, not hidden.

### Step 2: Apply Simplicity Principles

1. **Simplicity is the ultimate sophistication** - If it can be simpler, it should be
2. **Subtract, don't add** - Ask "what to remove" before "what to add"
3. **No thinking required** - Users should understand by instinct
4. **Consistency > Features** - One coherent system beats scattered features

### Step 3: Evaluate Each Option

For each option, ask:
- Can it be simpler without losing essential function?
- Does it require explanation to use?
- Does it break existing consistency?
- Is it adding accidental or essential complexity?

## Output

1. Restate the core problem (one sentence)
2. For each option: pros, cons, complexity type
3. Recommendation with clear reasoning
4. If no option is good: suggest a different framing

## Red Flags

- "Users will learn..." → They rarely do
- "We can add a setting for..." → Settings are failure of design
- "It's complex but powerful..." → Power users are 1%

## Balance Check

Before rejecting a complex option, verify:
- Is this complexity from the problem or the solution?
- Would a "simpler" option actually solve the problem?
- Am I over-applying simplicity dogma?

User knows their domain better than I do. If they insist on an approach I find complex, ask why before pushing back.

## Completion Criteria

- Comparison table presented (Rule 13 format)
- User has selected an approach
- If no option is suitable: alternative framing proposed and user acknowledged
