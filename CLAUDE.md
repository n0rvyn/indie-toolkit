# indie-toolkit

Multi-plugin monorepo for Claude Code plugins, published to the `indie-toolkit` marketplace.

## Plugin-specific Build Rules

### wechat-bridge

- Uses **esbuild bundle** (not plain tsc output). The MCP server runs in the plugin cache where `node_modules` doesn't exist; all dependencies must be inlined into the dist files.
- Build: `npm run build` = `tsc --noEmit` (type check only) + `esbuild` (bundle to `dist/`).
- Release artifacts in `dist/` must be self-contained single files. If a new dependency is added, verify it gets bundled — `--packages=external` is NOT used.

## Suggestion Hygiene (Anti-Fabrication Rule)

When closing out a response with a "next step" suggestion or follow-up plan:

**禁止**: 引用不存在的工作流入口。常见违例：
- "下一个 session 跑 /run-phase" — 没有 dev-guide 时禁止
- "继续执行计划" — 没有已写的 plan 文件时禁止
- "下一阶段" — 没有 phased dev-guide 时禁止
- "按既定流程" — 当流程并不存在时禁止

**自检**: 发出每一条 suggestion 前问：「我是否在引用一个具体存在的文件/状态机/已运行的 skill？」回答"我以为有"或"应该有"= 禁止发送。

**Why:** 主上下文 Claude 反复出现"凭空发明工作流"模式。这与全局 CLAUDE.md 的「未读不评 / 先验证再结论」是同一类失败的运行时表现。

**How to apply:** 在每次 response 结尾的"下一步"建议前停顿，对照已知 artifact 列表（plan file / dev-guide / state file / running task）。无对应 artifact → suggestion 改写为"如果你想 X，可以 ..."（条件式），不是"我建议下一步 Y"（断言式）。

## Skill Cost Posture

Every skill and agent SKILL.md / agent.md in this marketplace must declare a deliberate cost posture via `model:` / `effort:` / `context:` frontmatter. Skills that omit these inherit the session model (Opus by default in this team's setup), which silently charges ~20× a Sonnet turn for work Sonnet handles correctly.

**Authoritative heuristic + decision table**: `skill-master/skills/plugin-master/cost-posture.md`

**Quick reference** (classify by *dominant work at runtime*):

| Class | Config |
|---|---|
| Mechanical execution (follows pre-written plan/spec) | `model: sonnet` |
| Retrieval + extract (search corpus, return snippets) | `model: sonnet` + optional `context: fork agent: Explore` |
| Tool wrapper (CLI/API call, structured output) | `model: haiku` + `context: fork` |
| Judgment / Synthesis / Orchestration | inherit (do not downgrade) |

**When this rule fires:**

- **Creating a new skill/agent**: `skill-master:plugin-master` Step 2a.5 runs the cost posture recommendation; do not commit a new SKILL.md without it set or explicitly marked "keep inherit".
- **Auditing**: `skill-master:plugin-reviewer` Dimension 7.5 flags missing optimization (mechanical skill on inherit) AND misuse (judgment skill on haiku). Both directions matter.
- **Refactoring an existing skill**: if you change what a skill *does*, re-classify and update the posture.

**Why we enforce this**: real usage data over 3 days showed `execute-plan` running 626 turns on Opus ($487) vs 3054 turns on Sonnet ($103) — the Sonnet half worked, the Opus half was inherited default. The fix was a one-line frontmatter change per skill.

**Do not downgrade**: write-plan, brainstorm, design-decision, verify-plan, run-phase, fix-bug (diagnosis), review-execution, plugin-master itself. These do judgment / synthesis / orchestration; quality loss cascades downstream and costs more than the per-turn savings.

**Operating principles**: see `dev-workflow/skills/audit-tokens/SKILL.md §Principles` for the two governance rules (enhance-not-break; recover-unwarranted-cost-only).

## Plugin Lifecycle

### When Creating a New Plugin

1. **Create plugin directory** with `.claude-plugin/plugin.json`
2. **Add to `marketplace.json`**: add entry with `name`, `source`, `description`, `version`, `category`, `tags`
3. **Add to `.github/workflows/auto-version.yml`**:
   - Add plugin directory path to the `on.push.paths` list
   - Add plugin name to the `ALL_PLUGINS` array in the `push` branch of the sentinel discriminator (indie-toolkit native path only; downstream callers pass their own `plugins` input)
4. **Add to `.github/workflows/release-plugin.yml`**:
   - Add plugin name to the `target.options` list under `workflow_dispatch`
   - Add plugin name to `PLUGINS_WHEN_ALL_STR` in the `workflow_dispatch` branch of the sentinel discriminator (indie-toolkit native path only)
5. **Create plugin README** at `plugins/*/README.md`
6. **Update root `README.md`**: add plugin to the plugins table

### When Updating a Plugin

1. **Update plugin README**: ensure description, skills, agents, and architecture are current
2. **Update root `README.md`**: sync any description or metadata changes to the plugins table
3. **Update `marketplace.json`**: sync description and tags if changed

Version bumps happen automatically via `.github/workflows/auto-version.yml` (conventional commit based) or `.github/workflows/release-plugin.yml` (manual trigger).

## Shared Reusable Workflows

`.github/workflows/auto-version.yml` and `release-plugin.yml` both support invocation from downstream repos via `workflow_call`. Downstream repos (ops-toolkit, personal-os, etc.) should use a thin 5-line caller file.

### Pin Strategy

Downstream repos must pin to a specific tag, not `@main`:
- Recommended: `@workflows/v1` (mutable major version, picks up non-breaking changes within v1)
- Strict: `@<sha>` or `@workflows/v1.0.0` (if immutable patch tags are introduced in the future)

### auto-version Contract

| input | type | required | description |
|---|---|---|---|
| `plugins` | string | yes | Space-separated list of plugin directory names |
| `marketplace_tag_prefix` | string | yes | Marketplace metadata tag prefix (e.g., `ops-toolkit-`) |
| `marketplace_path` | string | no | Path to marketplace.json, default `.claude-plugin/marketplace.json` |

### release-plugin Contract

| input | type | required | description |
|---|---|---|---|
| `target` | string | yes | Plugin name or `all` |
| `bump` | string | yes | `patch` / `minor` / `major` |
| `plugins_when_all` | string | no | Space-separated list when target=all |
| `update_marketplace` | boolean | no | Default true |
| `create_tag` | boolean | no | Default true |
| `marketplace_tag_prefix` | string | yes | Same as above |
| `marketplace_path` | string | no | Same as above |

### Upgrade Impact

Changing internal implementation without touching inputs contract → no downstream impact (v1 patch).
Adding input with default → no downstream impact (v1 minor).
Removing/renaming input or changing default behavior → breaking, requires `workflows/v2`, downstream must migrate manually.

## Commit Message Convention

本仓使用 [Conventional Commits](https://www.conventionalcommits.org/) 配合 auto-version workflow 实现 semver 自动 bump。

**权威规范**：`dev-workflow/skills/commit/references/conventional-commits.md`（推荐通过 `/commit` skill 创建 commit，自动保证规范）。

**核心 type → bump 映射**：
- `feat` → minor | `fix` / `refactor` / `perf` / `chore` / `docs` / `test` → patch | 任意 type 加 `!`（如 `fix!`、`chore(api)!`）或 body 含 `BREAKING CHANGE` → major
- BREAKING `!` 必须在 scope 括号**后**：`feat(pkos)!:` 正确，`feat!(pkos):` 错误（后者静默 fallback 到 patch）

**Scope**：使用 plugin 名（如 `feat(dev-workflow):`），跨 plugin 用 `chore(release):` 或 `docs:`。

