# skill-master

Unified plugin lifecycle management: brainstorm, create, eval, review, iterate, and package Claude Code plugins and components.

## Install

```bash
/plugin install skill-master@indie-toolkit
```

## Usage

Single entry point:

```
/master
```

Routes to one of four workflows based on intent:

| Route | When | What happens |
|-------|------|-------------|
| **create** | "build a plugin", "create a skill" | brainstorm → design → scaffold (plugin-dev) → eval (skill-creator) → review → iterate |
| **review** | "review plugin", "audit my plugin" | 9-dimension audit + cross-plugin trigger conflict detection |
| **iterate** | "improve trigger", "fix this skill" | fix → re-eval → compare baseline → verify |
| **package** | "package plugin", "inject skill" | marketplace readiness check or inject into target project |

## Architecture

```
/master (intent detection)
   │
   ├── create ──→ intent-distiller → plugin-dev:create-plugin / skill-development
   │                                → skill-creator:skill-creator (eval loop)
   │                                → auto-review gate
   │
   ├── review ──→ plugin-dev:plugin-validator + skill-reviewer (Strategy A)
   │              skill-master:plugin-reviewer (9-dimension deep review)
   │              skill-master:trigger-arbiter (cross-plugin conflicts)
   │
   ├── iterate ─→ skill-creator scripts (run_loop.py, quick_validate.py)
   │              re-eval + baseline comparison
   │
   └── package ─→ plugin-dev:plugin-validator (structural)
                  skill-creator scripts (quick_validate.py, package_skill.py)
```

### Delegation Principle

skill-master orchestrates; it does not rebuild existing capabilities:

| Capability | Delegated to | How |
|-----------|-------------|-----|
| Plugin scaffolding | `plugin-dev:create-plugin` | Skill invocation |
| Skill writing guidance | `plugin-dev:skill-development` | Skill invocation |
| Agent writing guidance | `plugin-dev:agent-development` | Skill invocation |
| Agent generation | `plugin-dev:agent-creator` | Agent dispatch |
| Hook writing guidance | `plugin-dev:hook-development` | Skill invocation |
| Structural validation | `plugin-dev:plugin-validator` | Agent dispatch |
| Description quality | `plugin-dev:skill-reviewer` | Agent dispatch |
| Eval loop | `skill-creator:skill-creator` | Skill invocation |
| Description optimization | `skill-creator` run_loop.py | Bash |
| Skill packaging | `skill-creator` package_skill.py | Bash |

## Agents

| Agent | Model | Purpose |
|-------|-------|---------|
| plugin-reviewer | opus | 9-dimension deep review from AI executor perspective (migrated from skill-audit) |
| intent-distiller | sonnet | Extract structured plugin/skill development intent from user requests |
| trigger-arbiter | opus | Cross-plugin trigger overlap and conflict detection |

### Supporting Files

| File | Loaded when | Content |
|------|------------|---------|
| structural-validation.md | plugin-dev unavailable | D1 Structural Validation + D2 Reference Integrity |
| trigger-baseline.md | plugin-dev unavailable | D5.1-5.2 description overlap + D7.3 description quality + D9.1 trigger quality |

## Skills

| Skill | Description |
|-------|-------------|
| master | Single entry point with 4-route intent detection. Orchestrates full plugin lifecycle. |

## Review Dimensions

The review route covers 9 dimensions, with ownership split based on plugin-dev availability:

| # | Dimension | Strategy A Owner | Strategy B Owner |
|---|-----------|-----------------|-----------------|
| D1 | Structural Validation | plugin-dev:plugin-validator | plugin-reviewer + structural-validation.md |
| D2 | Reference Integrity | plugin-dev:plugin-validator | plugin-reviewer + structural-validation.md |
| D3 | Workflow Logic | plugin-reviewer (core) | plugin-reviewer (core) |
| D4 | Execution Feasibility | plugin-reviewer (core) | plugin-reviewer (core) |
| D5 | Trigger & Routing | split: baseline → skill-reviewer; deep → plugin-reviewer | plugin-reviewer (full) |
| D6 | Edge Cases & False Results | plugin-reviewer (core) | plugin-reviewer (core) |
| D7 | Spec Compliance | split: D7.3 → skill-reviewer; rest → plugin-reviewer | plugin-reviewer (full) |
| D8 | Metadata & Docs | plugin-reviewer (core) | plugin-reviewer (core) |
| D9 | Trigger Quality | split: D9.1 → skill-reviewer; rest → plugin-reviewer | plugin-reviewer (full) |
| + | Cross-Plugin Conflicts | trigger-arbiter | trigger-arbiter |

## Optional Dependencies

- `plugin-dev` — for component creation guidance and structural validation
- `skill-creator` — for eval loop, description optimization, and packaging scripts

Without these, skill-master falls back to manual workflows and self-contained review (Strategy B).

## Migration from skill-audit

skill-master absorbs all skill-audit capabilities. If you have skill-audit installed:

1. Install skill-master: `/plugin install skill-master@indie-toolkit`
2. Use `/master` with "review" intent instead of `/plugin-review`
3. Optionally uninstall skill-audit: `/plugin uninstall skill-audit`
