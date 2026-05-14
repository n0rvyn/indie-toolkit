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

## Plugin Lifecycle

### When Creating a New Plugin

1. **Create plugin directory** with `.claude-plugin/plugin.json`
2. **Add to `marketplace.json`**: add entry with `name`, `source`, `description`, `version`, `category`, `tags`
3. **Add to `.github/workflows/auto-version.yml`**:
   - Add plugin directory path to the `on.push.paths` list (line 7-17)
   - Add plugin name to `ALL_PLUGINS` array (line 45)
4. **Add to `.github/workflows/release-plugin.yml`**:
   - Add plugin name to the `target.options` list (line 11-22)
   - Add plugin name to `PLUGINS` array if `TARGET == "all"` (line 87)
5. **Create plugin README** at `plugins/*/README.md`
6. **Update root `README.md`**: add plugin to the plugins table

### When Updating a Plugin

1. **Update plugin README**: ensure description, skills, agents, and architecture are current
2. **Update root `README.md`**: sync any description or metadata changes to the plugins table
3. **Update `marketplace.json`**: sync description and tags if changed

Version bumps happen automatically via `.github/workflows/auto-version.yml` (conventional commit based) or `.github/workflows/release-plugin.yml` (manual trigger).

## Commit Message Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/) with automated semver bumping.

### Format

```
<type>(<scope>): <description>

[optional body]
```

### Types

| Type | Bump | When |
|------|------|------|
| `feat` | minor | New feature |
| `fix` | patch | Bug fix |
| `docs` | patch | Documentation only |
| `refactor` | patch | Code change that neither fixes a bug nor adds a feature |
| `perf` | patch | Performance improvement |
| `test` | patch | Adding or correcting tests |
| `chore` | patch | Build process, auxiliary tools, or dependency updates |
| `feat!` or `BREAKING CHANGE` in body | major | Breaking change |

### Scoping

Scope should reference the plugin or concern being changed:
- `feat(dev-workflow):`, `fix(apple-dev):`, `docs(mactools):`
- For changes spanning multiple plugins: `chore(release):`, `docs:`

### Auto-Version Bump

`.github/workflows/auto-version.yml` detects the highest bump type from commit messages and bumps:
- All changed plugins (each plugin's `version` in its `plugin.json`)
- The marketplace `metadata.version` (highest bump among changed plugins)

Commits from `github-actions[bot]` are excluded from bump detection.

### Examples

```
feat(domain-intel): add GitHub API rate limit handling
fix(apple-dev): correct SwiftData migration guide for iOS 26
docs: update wechat-bridge README with new auth flow
feat!(pkos): change inbox routing to require explicit destination
chore: bump dependencies across all plugins
```

