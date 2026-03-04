# Indie Toolkit

Skills and plugins for:

- iOS/macOS development (`ios-development`)
- macOS automation (`mactools`)
- Cross-stack dev workflow orchestration (`dev-workflow`)
- Product evaluation for indie devs (`product-lens`)
- Local docs RAG MCP server (`rag-server`)
- Plugin/skill audit tooling (`skill-audit`)

## Claude Code

Add marketplace:

```bash
/plugin marketplace add n0rvyn/indie-toolkit
```

Install plugin(s):

```bash
/plugin install dev-workflow@indie-toolkit
/plugin install ios-development@indie-toolkit
/plugin install mactools@indie-toolkit
/plugin install product-lens@indie-toolkit
/plugin install rag-server@indie-toolkit
/plugin install skill-audit@indie-toolkit
```

Available plugins:

| Plugin | What it does | Docs |
|---|---|---|
| `dev-workflow` | Plan → execute → review workflow with agent dispatching and hooks | `dev-workflow/README.md` |
| `ios-development` | iOS/macOS/iPadOS development workflows | `ios-development/README.md` |
| `mactools` | macOS automation (Notes/Calendar/Mail/Safari/Spotlight/…) | `mactools/README.md` |
| `product-lens` | Indie product evaluation (`/evaluate`, `/compare`, …) | `product-lens/README.md` |
| `rag-server` | Local hybrid search MCP server (BM25 + vectors) | `rag-server/README.md` |
| `skill-audit` | Review other plugins/skills from executor perspective | `skill-audit/README.md` |

Notes:
- `rag-server` needs extra setup (Python venv + compiling embed binary); follow `rag-server/README.md` after installing.

## Codex

Tell Codex:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/n0rvyn/indie-toolkit/main/.codex/INSTALL.md
```

Detailed docs: `docs/README.codex.md`

## OpenCode

Tell OpenCode:

```text
Fetch and follow instructions from https://raw.githubusercontent.com/n0rvyn/indie-toolkit/main/.opencode/INSTALL.md
```

Detailed docs: `docs/README.opencode.md`
