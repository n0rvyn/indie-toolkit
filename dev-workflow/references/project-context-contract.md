# Project Context Contract

Use this reference when a skill or agent needs project language, source ownership, module map, or validation commands.

## File Roles

| File | Role |
|------|------|
| `CLAUDE.md` | Execution rules for Claude Code in this project. |
| `AGENTS.md` | Execution rules for agent runtimes in this project. |
| `docs/00-AI-CONTEXT.md` | Product language, user-visible object names, module map, source-of-truth notes, and validation commands. |
| plan/dev-guide/crystal files | Task-specific contracts, phase scope, and settled decisions. |

## Loading Rules

1. If `docs/00-AI-CONTEXT.md` exists, read it before writing a plan, writing a dev-guide, diagnosing a bug, verifying a plan, or reviewing implementation.
2. Treat `docs/00-AI-CONTEXT.md` as the source for user-visible names and product terms.
3. Treat `CLAUDE.md` and `AGENTS.md` as execution-rule files, not product-language files.
4. If `docs/00-AI-CONTEXT.md` is missing, continue and mark `Project context contract: missing`.
5. Do not create `CONTEXT.md`. Keep the project context contract at `docs/00-AI-CONTEXT.md`. (DP: this project's policy reserves repo-root `CONTEXT.md` for non-context purposes; Pocock's `mattpocock/skills` repo uses `CONTEXT.md` at root, but the structural ideas — Language/Relationships/Flagged ambiguities — are absorbed under our path.)

## Recommended Structure for `docs/00-AI-CONTEXT.md`

Adopted from Eric Evans' Domain-Driven Design *ubiquitous language* concept (via Matt Pocock's `mattpocock/skills` `grill-with-docs` skill). When you create or update `docs/00-AI-CONTEXT.md`, organize content under these three sections:

```markdown
# {Project / Context Name}

{One or two sentence description of what this context is and why it exists.}

## Language

**Term1**:
A concise one-sentence definition (define what it IS, not what it does).
_Avoid_: alias1, alias2

**Term2**:
A concise one-sentence definition.
_Avoid_: alias1

## Relationships

- A **Term1** produces one or more **Term2**
- A **Term2** belongs to exactly one **Term1**

## Flagged ambiguities

- "alias1" was used to mean both **Term1** and **Term2** — resolved: these are distinct concepts.
```

### Rules
- **Be opinionated.** When multiple words exist for the same concept, pick the best one and list the others as `_Avoid_:` aliases.
- **Flag conflicts explicitly.** If a term was used ambiguously in the past, call it out under `## Flagged ambiguities` with a clear resolution.
- **Tight definitions.** One sentence max per term. Define what it IS, not what it does.
- **Show relationships.** Use bold term names; express cardinality where obvious.
- **Project-specific only.** General programming concepts (timeouts, error types, utility patterns) don't belong even if used. Ask: is this concept unique to this context, or generic?
- **Optional `## Example dialogue`.** A short conversation between a dev and domain expert can clarify boundaries between related concepts.

### Multi-context monorepos

For repos with multiple bounded contexts:
- A `CONTEXT-MAP.md`-equivalent section in `docs/00-AI-CONTEXT.md` (or a separate `docs/00-CONTEXT-MAP.md`) lists each context, where its contract lives, and how contexts relate.
- Per-bucket contracts can live at `docs/00-AI-CONTEXT-{bucket}.md`.

## Conflict Handling

- If `CLAUDE.md` and `AGENTS.md` disagree on a process requirement, surface a blocking decision instead of choosing silently.
- If `docs/00-AI-CONTEXT.md` uses product names that differ from a plan or review output, cite the file and require the plan/review to use product text or real UI/source text.
- If validation commands differ across context docs, list both commands and ask for a blocking decision before execution.
