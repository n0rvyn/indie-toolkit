# skill-audit

Review Claude Code plugins, skills, agents, hooks, and commands from the AI executor perspective.

## Claude Code

Install from indie-toolkit marketplace:

```bash
/plugin install skill-audit@indie-toolkit
```

## Usage

- `/plugin-review` — dispatches the `plugin-reviewer` agent to audit a plugin or specific artifacts.

## Agents

| Agent | Model | Description |
|-------|-------|-------------|
| plugin-reviewer | opus | Reviews plugin artifacts from AI executor perspective. Covers 9 dimensions: structural validation, reference integrity, workflow logic, execution feasibility, trigger & routing, edge cases, spec compliance, metadata & docs, and **Trigger Quality Review** (new in Phase 3). |

## Skills

| Skill | Description |
|-------|-------------|
| plugin-review | Dispatches plugin-reviewer agent to review plugin artifacts. Now supports eval.md files for trigger plausibility checking. |

## Trigger Quality Review (Phase 3)

The plugin-reviewer now includes a **Trigger Quality Review** dimension (Dimension 9) that:

- Checks skill descriptions have clear trigger scenarios ("Use when/for/after/before", "当...时使用")
- Validates eval.md trigger tests (if present) against skill descriptions for plausibility
- Detects cross-skill trigger conflicts (e.g., `design-review` vs `ui-review` both matching "review UI")
- Produces a **Trigger Health Score** per skill: `pass` / `warn` / `fail`

### Trigger Health Score Output

After running `/plugin-review`, the report includes:

```
### Trigger Health Score

| Skill | Description Quality | Eval Coverage | Conflict Check | Verdict |
|-------|--------------------|---------------|----------------|---------|
| skill-name | pass | pass | pass | pass |
```

- **Description Quality**: pass/warn/fail based on trigger clarity
- **Eval Coverage**: pass/fail/N/A (N/A if no eval.md exists)
- **Conflict Check**: pass/warn/fail based on cross-skill trigger overlap
- **Verdict**: overall trigger health for the skill
