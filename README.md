# Indie Toolkit

Multi-plugin monorepo for Claude Code plugins, published to the `indie-toolkit` marketplace. Contains production plugins, development workflow tools, and macOS automation.

## Plugins

| Plugin | Category | Description |
|--------|----------|-------------|
| `dev-workflow` | development | Cross-stack workflow system with plan-execute-review lifecycle, phase orchestration, and session state persistence |
| `apple-dev` | development | iOS/macOS/iPadOS development: review agents, design parity, visual audit, runtime feature verification, CI/CD, App Store review prep |
| `mactools` | productivity | macOS automation for Notes, Calendar, Mail, Safari, Spotlight, Reminders, OCR, Photos, Contacts, OmniFocus |
| `product-lens` | product | Product evaluation: demand validation, market analysis, moat assessment, feature assessment, comparison matrix |
| `skill-master` | development | Unified plugin lifecycle: brainstorm, create, eval, review, iterate, package Claude Code plugins. Entry: `/plugin-master` |
| `shared-utils` | development | Reusable utility scripts and skills shared across plugins: Notion API, MongoDB queries, cross-plugin primitives |
| [readback](readback/README.md) | development | Before-action read-back protocol: non-blocking one-line "here's the reading I picked" on ambiguous requests, full plain-language echo on `/readback` and `/fix-bug` (4 hooks + 1 agent + 1 skill) |
| [miniprogram](miniprogram/README.md) | development | WeChat mini program QA: headless UI verification against running devtools (screenshot + `page.data()` + geometry), and pre-submission config/compliance checks |

## Repository Layout

```text
.
├── dev-workflow/
├── apple-dev/
├── mactools/
├── product-lens/
├── skill-master/
├── shared-utils/
├── docs/
├── .claude-plugin/   # marketplace manifest
├── .codex/           # Codex install docs
└── .opencode/        # OpenCode install docs
```

## Claude Code

Add the marketplace:

```bash
/plugin marketplace add n0rvyn/indie-toolkit
```

Install plugins:

```bash
/plugin install dev-workflow@indie-toolkit
/plugin install apple-dev@indie-toolkit
/plugin install mactools@indie-toolkit
/plugin install product-lens@indie-toolkit
/plugin install skill-master@indie-toolkit
/plugin install shared-utils@indie-toolkit
```

For personal OS plugins — `/health`, `/reflect`, `/intel`, `/scout`, `/pkos`, `/portfolio-scan` and related — see the [personal-os marketplace](https://github.com/n0rvyn/personal-os).

Versions are not duplicated here — `.claude-plugin/marketplace.json` is the authority, and `auto-version` bumps it on every release.

## Codex / OpenCode

Both Codex and OpenCode use file-based installation. The sources of truth are:

- Codex: `.codex/INSTALL.md`
- OpenCode: `.opencode/INSTALL.md`

Skills for each platform are linked via these install guides. Each plugin's `skills/` folder contains its skill definitions.

## Plugin Docs

Each plugin has its own `README.md`:

- `dev-workflow/README.md` — Cross-stack workflow system
- `apple-dev/README.md` — iOS/macOS/iPadOS development
- `mactools/README.md` — macOS automation
- `product-lens/README.md` — Product evaluation
- `skill-master/README.md` — Plugin lifecycle management
- `shared-utils/README.md` — Reusable cross-plugin utility scripts and skills
