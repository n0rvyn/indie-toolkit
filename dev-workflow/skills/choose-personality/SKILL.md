---
name: choose-personality
description: "Use when starting a new project's design phase, before /generate-design-system. Asks 6 personality dimensions interactively and writes docs/02-architecture/design-personality.md. Not when: project already has a design system locked, or user is mid-implementation."
---

# Choose Personality Skill

Lock the project's visual + linguistic personality early — vibe, audience, formality, font character, radius personality, language tone — so downstream design-system generators have grounded inputs instead of asking the user to make these decisions component-by-component.

## Hard Gate

The skill operates relative to the **current working directory** (treated as the project root). If `docs/02-architecture/design-personality.md` does not exist, proceed directly to Step 1.

If the file exists, decide whether the user wants to regenerate it. The decision MUST come from the user's most recent message in the conversation, not from skill invocation arguments alone (slash-command arguments are not always preserved through skill resolution).

**Regenerate intent — proceed:**
- Most recent user message contains the literal token `--regenerate` (case-sensitive).
- English: "regenerate" / "overwrite" / "rewrite" appearing as a verb modifying "personality file" / "personality" / "this file" / "design-personality.md".
- Chinese: "重新生成" / "重写" / "覆盖" directly modifying "personality" / "personality 文件" / "这个文件" / "design-personality.md".

**Refuse and stop — print and exit:**
> Personality file already exists at `docs/02-architecture/design-personality.md`.
> To regenerate from scratch, say "regenerate the personality file" or invoke with `--regenerate`.

**Ambiguous (most common case — neither clearly regenerate nor clearly not):** use `AskUserQuestion` with two options:
- "Regenerate from scratch (overwrite existing file)"
- "Cancel — keep existing personality"

Do NOT guess. The cost of guessing wrong is overwriting the user's previously-locked design personality, which is irreversible without git.

Only proceed past this gate when:
- The file does not exist, OR
- Regenerate intent is unambiguous per the rules above, OR
- The user picks "Regenerate from scratch" via `AskUserQuestion`.

## Process

### 1. Read methodology source

Read `dev-workflow/references/refactoring-ui-distilled.md` Section D (Personality Framework). The 6 dimensions and example values come from this section.

### 2. Ask 6 questions one at a time

Use AskUserQuestion. AskUserQuestion caps at **4 options** per question; users always get an automatic "Other (free text)" entry, so present at most **3 explicit options** below and let less common choices come through Other. Ask in this order, one per call:

- **Q1 — Vibe**: "What's the overall vibe?" — options: playful / serious / utilitarian (full menu in description: playful, serious, aggressive, calm, luxurious, utilitarian)
- **Q2 — Audience**: "Who's the user?" — options: mass consumer / power user / specialist (full menu: mass consumer, power user, executive, hobbyist, specialist)
- **Q3 — Formality**: "How formal is the language?" — options: casual / neutral / formal
- **Q4 — Font character**: "What font family fits?" — options: geometric sans / humanist sans / serif (full menu: geometric sans, humanist sans, serif, display, monospace)
- **Q5 — Radius personality**: "How sharp or rounded?" — options: sharp (0–2pt) / medium (4–8pt) / rounded (12–16pt). Pill (full) is reachable via Other for niche cases.
- **Q6 — Language tone**: "How does the product speak?" — options: terse / explanatory / encouraging (professional is reachable via Other)

For each question: present 3 explicit options; mention the broader menu in the question description so users know what Other can carry. Do NOT proceed to the next question until the current one is answered.

### 3. Propose color and font candidates

Based on the 6 answers, propose:
- **2 candidate primary colors** (hex + HSL), each justified by one sentence linking back to vibe + audience + formality
- **2 candidate font families**, each justified by one sentence linking to font character + audience

Ask the user to pick one of each via AskUserQuestion (single-select per question).

### 4. Derive radius scale and language register

Map the radius personality answer to a concrete scale:
| Answer | Scale (small / medium / large) |
|--------|--------------------------------|
| sharp | 0pt / 2pt / 4pt |
| medium | 4pt / 8pt / 12pt |
| rounded | 12pt / 16pt / 24pt |
| pill | 999pt (full) for all |

**If the Q5 answer arrived via Other (free text):** map it to the closest table row by the user's intent — `pill` / `full` / `circular` → pill; `sharp` / `crisp` / `square` → sharp; `medium` / `balanced` → medium; `rounded` / `soft` / `friendly` → rounded. If the free-text answer doesn't fit any row, re-ask via `AskUserQuestion` with the four explicit options before deriving the scale. Never invent a scale outside the table.

Map the language tone answer to register notes (3–5 sentences). Use this skeleton table — fill the bracketed slots with project-specific details from prior answers (vibe / audience / formality):

| Tone | Error messages | Empty states | Microcopy |
|------|---------------|--------------|-----------|
| terse | One short sentence stating what failed; no apology. | One line + one CTA. | Verb-first labels ("Save", not "Click here to save"). |
| explanatory | Two sentences: what happened + how to fix. | Two-sentence "what this is" + CTA. | Help text under fields when value is non-obvious. |
| encouraging | Empathetic phrasing ("Let's try that again"); blame the system, not the user. | Reframe absence as opportunity ("Start your first [thing]"). | Action verbs softened ("Add" over "Submit"). |
| professional | Neutral, formal: state the condition + remediation step. | Brief description + primary action. | No exclamation marks; no contractions. |

### 5. Write `docs/02-architecture/design-personality.md`

**Sanity checks before writing:**
- Picked hex must match `^#[0-9A-Fa-f]{6}$`. If the proposed colors don't, regenerate the candidates.
- Picked font: note whether it's a system font (e.g. SF Pro on Apple platforms, system) or requires a third-party install. Record the answer in the file's Picked Font section as `System font: yes/no`.
- Replace every `YYYY-MM-DD` placeholder below with today's actual date.

Format:

    ---
    type: design-personality
    created: YYYY-MM-DD
    ---

    # Project Design Personality

    ## 6 Dimensions
    - Vibe: <answer>
    - Audience: <answer>
    - Formality: <answer>
    - Font character: <answer>
    - Radius personality: <answer>
    - Language tone: <answer>

    ## Picked Primary Color
    - Hex: <#RRGGBB>            <!-- consumer contract: read by apple-dev:generate-design-system -->
    - HSL: <h, s%, l%>          <!-- human reference; consumers read Hex -->
    - Justification: <one-sentence>

    ## Picked Font
    - Family: <name>
    - System font: <yes/no>
    - Justification: <one-sentence>

    ## Derived Radius Scale
    - small: <Npt>
    - medium: <Npt>
    - large: <Npt>

    ## Language Register Notes
    <3–5 sentence guidance for error messages, empty states, microcopy — derived from the tone-mapping table in Step 4>

    ## Source
    - Methodology: dev-workflow/references/refactoring-ui-distilled.md Section D
    - Generated by: dev-workflow:choose-personality on YYYY-MM-DD

### 6. Output recommendation

After writing the file, print:

> Personality locked at `docs/02-architecture/design-personality.md`.
> Next: the `generate-design-system` skill will be auto-invoked (when triggered via run-phase or design-related prompts) to produce the platform-specific design system code grounded in these inputs.

## Completion Criteria

- All 6 questions answered (or hard gate triggered)
- 1 color + 1 font picked from proposed candidates
- `docs/02-architecture/design-personality.md` written and contains all required sections
- User informed of next step

## Dispatch

Main session — interactive (uses AskUserQuestion). Do NOT dispatch as a sub-agent.
