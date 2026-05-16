# Ubiquitous Language (reference)

A small project-level glossary that maps codebase identifiers to plain-language meanings, so the AI, the user, and any domain expert all share one vocabulary when planning, debugging, and reviewing.

Origin: Domain-Driven Design (Eric Evans). Modernized for AI collaboration by Matt Pocock — "essentially a markdown file full of a list of terms that you and the AI have in common." This reference adapts the practice for dev-workflow skills.

## Why this exists

Two symptoms tell you the project needs one:

1. **The AI is verbose** — it produces long-winded restatements because it doesn't know the project's domain shorthand. A `Booking` is just a `Booking`; once both sides agree on that, the AI stops paraphrasing.
2. **Identifier vs. user-facing-term mismatch** — code uses `aurora_metric` but the UI says "Reading", and the AI invents a third term ("metric value") in chat. The user has to translate twice per conversation.

A ubiquitous-language doc collapses this gap. The AI reads it, uses the canonical term, and reasoning traces become noticeably shorter (Matt Pocock's observation: "thinking traces become less verbose, implementation more aligned with the plan").

## File location

```
docs/02-architecture/ubiquitous-language.md
```

Single file at the project root level. Not per-module. If a module's terms diverge significantly from the rest of the project, that itself is a signal worth surfacing — a separate file hides it.

## Structure

```markdown
---
type: ubiquitous-language
status: active
last_updated: YYYY-MM-DD
---

# Ubiquitous Language

## Domain Terms

| Term (canonical) | Code identifier(s) | Plain meaning | Aliases to avoid |
|------------------|--------------------|---------------|------------------|
| Reading | `AuroraMetric`, `metric_value` | A single data point sampled from the user — e.g., one weight entry, one mood log | "metric", "measurement", "data point" |
| Cycle | `MenstrualCycle`, `cycle_record` | One complete period-to-period interval; not the same as a calendar month | "month", "period span" |
| Trend Line | `aurora_trend.line` | The smoothed curve drawn over a series of Readings — visual, not a stored entity | "graph", "chart line" |

## UI Surfaces

| User-facing label | Refers to | Where it appears |
|-------------------|-----------|------------------|
| "Today's Reading" | The most recent Reading entered today | Home tab, Insight card |
| "Cycle Day N" | Day N of the active Cycle | Cycle tab header |

## Reserved / Forbidden

| Term | Why forbidden | Use instead |
|------|---------------|-------------|
| "user data" | Too vague — ambiguous between Readings, profile, settings | Specify which entity |
| "sync" | Used for three different mechanisms — backup, device handoff, server push | Name the mechanism explicitly |
```

Keep tables tight. Each row should fit on one screen line. If a meaning needs a paragraph, the term is poorly chosen — refine the term or split into two.

## When to maintain

**Add or update entries when:**
- A new feature introduces a domain noun the team has been verbalizing (3+ session mentions = needs an entry)
- The user corrects the AI's terminology twice ("we call it X, not Y")
- A rename happens in code that doesn't match the user-facing label
- A `brainstorm` session settles on a name for something previously unnamed

**Do NOT add:**
- Pure code structure terms (function names, class names with obvious meaning)
- Standard framework vocabulary (React, SwiftUI, etc.)
- Internal implementation details (cache key names, env var names)

## How dev-workflow skills consume this file

- `brainstorm` Step 1: reads the file if present; uses canonical terms in clarifying questions; at Step 6 suggests updating if recurring domain terms emerged
- `write-plan` Step 1: reads alongside `docs/00-AI-CONTEXT.md`; plan tasks use canonical terms in `Expected behavior`, `User interaction`, and `Touched surface` fields
- `fix-bug` Step 0.8: reads if present; uses canonical terms in `Task Contract.Expected behavior` and `[值域检查]` table rows
- `feature-spec-writer`: reads if present; feature specs use canonical terms in user journey descriptions

Skills should read but not auto-write the file — updates require explicit user confirmation (the file is a shared contract, not session state).

## Distinguishing from other docs

| Doc | Purpose | Audience |
|-----|---------|----------|
| `CLAUDE.md` | Project rules and constraints for AI | AI only |
| `docs/00-AI-CONTEXT.md` | Project source-of-truth contract (which dirs, which build commands, which test commands) | AI + new contributors |
| `docs/02-architecture/ubiquitous-language.md` | Term ↔ identifier ↔ meaning mapping | AI + domain experts + developers |
| `docs/06-plans/*-design.md` | Specific feature design | AI + reviewers |

Ubiquitous-language is the only file shared across all three audiences. That's the point: it's the translation layer.

## Anti-patterns

- **Letting the file rot**: a stale glossary is worse than none — the AI cites obsolete terms with confidence. Set a check at `finalize` time to flag entries unmentioned in any commit message or session log for 60+ days.
- **Code-identifier-to-code-identifier mapping**: if your "plain meaning" column reads like another identifier, the term hasn't actually been translated. Read it aloud to a non-developer to test.
- **Treating it as documentation**: it's a contract, not docs. Don't pad with paragraphs of background — that belongs in `docs/02-architecture/` proper.

## Source

Matt Pocock, "Software Fundamentals Matter More Than Ever" (talk, 2025) — `references/grill-protocol.md` cites the same talk for the grill-me pattern; both come from the same insight (codebase fundamentals matter MORE in the AI era, not less).
