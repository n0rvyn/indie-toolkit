# Indie Toolkit

Multi-plugin monorepo for Claude Code plugins, published to the `indie-toolkit` marketplace. Contains production plugins, development workflow tools, and macOS automation.

## Plugins

| Plugin | Category | Description |
|--------|----------|-------------|
| `dev-workflow` | development | Cross-stack workflow system with plan-execute-review lifecycle, phase orchestration, and session state persistence |
| `apple-dev` | development | iOS/macOS/iPadOS development workflows, reviews, design-token checks, CI/CD, localization, App Store review prep |
| `mactools` | productivity | macOS automation for Notes, Calendar, Mail, Safari, Spotlight, Reminders, OCR, Photos, Contacts, OmniFocus |
| `product-lens` | product | Product evaluation: demand validation, market analysis, moat assessment, feature assessment, comparison matrix |
| `skill-master` | development | Unified plugin lifecycle: brainstorm, create, eval, review, iterate, package Claude Code plugins |
| `skill-audit` | development | [DEPRECATED — use skill-master] Plugin auditor from AI executor perspective |
| `domain-intel` | intelligence | Domain intelligence engine: GitHub, RSS, changelogs, figures, companies, deep research with evolving LENS profiles |
| `session-reflect` | coaching | AI collaboration coach: analyze sessions, improve prompting, workflow, and AI collaboration skills |
| `youtube-scout` | intelligence | YouTube video intelligence: scrape, transcript extraction, AI scoring, IEF-compliant export |
| `pkos` | productivity | Personal Knowledge Operating System: inbox, harvest, signal, digest, lint, vault operations, ripple compilation |
| `wechat-bridge` | integration | WeChat message bridge via MCP `--channels` protocol: permission relay, push messages, reply |
| `x-api` | integration | X (Twitter) API v2 MCP server: 131+ tools with Bearer Token and OAuth2 PKCE support |

## Repository Layout

```text
.
├── dev-workflow/
├── apple-dev/
├── mactools/
├── product-lens/
├── skill-master/
├── skill-audit/
├── domain-intel/
├── session-reflect/
├── youtube-scout/
├── pkos/
├── wechat-bridge/
├── x-api/
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
/plugin install domain-intel@indie-toolkit
/plugin install session-reflect@indie-toolkit
/plugin install youtube-scout@indie-toolkit
/plugin install pkos@indie-toolkit
/plugin install wechat-bridge@indie-toolkit
/plugin install x-api@indie-toolkit
```

Current marketplace entries from `.claude-plugin/marketplace.json`:

| Plugin | Version | Description |
|---|---|---|
| `dev-workflow` | `2.23.0` | Cross-stack workflow with plan-execute-review |
| `apple-dev` | `1.10.2` | iOS/macOS/iPadOS development workflows |
| `mactools` | `1.0.1` | macOS automation for Apple apps |
| `product-lens` | `1.0.0` | Product evaluation and market analysis |
| `skill-master` | `1.0.0` | Unified plugin lifecycle management |
| `skill-audit` | `1.1.3` | [DEPRECATED] Plugin auditor |
| `domain-intel` | `1.4.0` | Domain intelligence and trend analysis |
| `session-reflect` | `2.0.0` | AI collaboration coaching |
| `youtube-scout` | `1.0.1` | YouTube video intelligence |
| `pkos` | `0.6.0` | Personal Knowledge OS |
| `wechat-bridge` | `1.0.3` | WeChat message bridge |
| `x-api` | `1.0.0` | X (Twitter) API v2 MCP server |

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
- `skill-audit/README.md` — Plugin audit (deprecated)
- `domain-intel/README.md` — Domain intelligence engine
- `session-reflect/README.md` — AI collaboration coach
- `youtube-scout/README.md` — YouTube intelligence
- `pkos/README.md` — Personal Knowledge OS
- `wechat-bridge/README.md` — WeChat bridge
- `x-api/README.md` — X API v2 MCP server
