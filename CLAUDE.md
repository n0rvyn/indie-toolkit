# indie-toolkit

Multi-plugin monorepo for Claude Code plugins, published to the `indie-toolkit` marketplace.

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

## Refactor Closure (跨 skill 改动收尾)

改一个 skill 的对外契约（谁调它、传什么、返回什么）时，两条硬规则：

**1. 断言旧行为的 eval，会给新 bug 放行。**

改 SKILL.md 之前，先 grep 一遍 `*/eval.md` 里有没有断言旧行为的条目。实证 2026-09-04：`execute-plan/SKILL.md:128` 从 `Suggest implementation-reviewer` 改成真调用，而 `execute-plan/eval.md:17` 断言的正是 `Output suggests implementation-reviewer` —— **那条 eval 会绿着放行刚被修掉的缺陷**。测试写的是旧行为时，它从守卫变成帮凶。

**自检**：我改的这个行为，有没有哪个 eval.md 正在断言它的反面？

**2. 「改完了」是 grep 出来的，不是想出来的。**

同一次改动里，我先凭印象说「全套关联的都弄完了」，用户追问后 grep 出 **6 处漏网**（另一个 skill 保留着自己的 agent 清单、两个 eval.md、README、两处 checklist）。

**动作**：声明收尾前跑一遍 `python3 .claude/skills/call-graph/scripts/call_graph.py --plugin <name>`（本地工具，`.claude/` 未纳入版本控制），核对新边出现、旧边消失；再 grep 一次被改行为的关键词。**⚠️ 静态图只能证明「边接对了」，证明不了运行时行为对** —— 契约类改动仍需一次真实运行。

**3. 靠段落名跨环节传数据的，加一个检查器。**

`reviewer agent → review-execution → run-phase` 这条链靠 markdown 段名逐字搬运，三端都是散文，没有任何东西在运行时校验。2026-09-04 一天之内断了两次：一次是 agent 只返回计数而 dispatcher 承诺逐字透传，一次是 `gated` 把交回内容截断成 must-fix。两次都没有测试发现，因为没有测试。

`python3 .claude/skills/call-graph/scripts/check_section_contract.py`（同为本地工具）核对三端段名一致；`--selftest` 先证明它能红。

⚠️ **这条链在本仓测不了**：`HAS_VIEW_MODIFIED` / `HAS_NEW_VIEW` 匹配 `*View.swift`，本仓 9 个 `.swift` 里 0 个符合、0 个 Xcode 工程 —— 三个 Apple reviewer 在这里从不会被派出。真正的端到端只能在 Apple 项目里改一个 View 时发生。**所以在这儿，段名一致是唯一可得的验证形式，不要把它当成「跑通了」。**

## 退役记录（`docs/12-retired/`）

**做新 skill 之前，先 `grep` 一遍 `docs/12-retired/`。** 十有八九以前做过 —— 里面记的是「当初为什么做、后来为什么不要了、再做要哪里不一样」，这些从 git log 重建不出来。

**退掉一个 skill 之前，先写记录，再删目录。** 顺序反了就写不出来了：理由只在当轮的上下文里，目录一没，剩下的只有 diff。

形态判据（2026-09-04 从九次退役里归纳，全文在该目录 README）：只读检查 → `review-execution` 下的一个 lens；生成/写入 → 保留 skill；读一份参考再复述 → reference，挂进 `apple-swift-context` 的 Topic Router。**大多数「死掉的 skill」不是内容不好，是形态选错了。**

## Plugin Lifecycle

### When Creating a New Plugin

> **Exception — Claude Design host plugins:** A plugin that runs *inside Claude Design* (not Claude Code) — currently `design-handoff/` — is intentionally **NOT** added to `marketplace.json`, **NOT** added to `auto-version.yml` (`ALL_PLUGINS` + `paths`), and **NOT** added to `release-plugin.yml`. It is vendored into the repo only for raw-URL distribution to Claude Design's contract pipeline. See `design-handoff/README.md` § "Why in repo but NOT in marketplace". Do **NOT** "fix" its absence from these files — the absence is deliberate. (The steps below apply only to real Claude Code plugins.)

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

### Input Contracts

Read `on.workflow_call.inputs` in `.github/workflows/auto-version.yml` and `release-plugin.yml` — that is the authoritative contract (names, types, required flags, defaults).

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

