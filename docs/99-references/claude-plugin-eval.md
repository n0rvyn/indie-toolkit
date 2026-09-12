# `claude plugin eval` — 调研与实测记录

日期 2026-09-12 · Claude Code 2.1.269 · 官方文档 https://code.claude.com/docs/en/plugin-evals

规则正本在 `skill-master/skills/plugin-master/eval-rules.md`（随插件发布）。本文件只放证据：结论从哪来、哪些实测过、哪些还没验证。跨项目的平台事实另见 `~/.claude/knowledge/platform-constraints/2026-09-12-claude-plugin-eval-isolation-and-graders.md`。

## 结论

- `claude plugin eval` 是**执行器**：真实起 `claude -p`、只加载被测插件、每个用例默认跑 3 次，外加一组不加载插件的对照，给出分差 Δ。
- 本仓的 `eval.md` 是**规格**：`.py/.sh/.js/.ts` 里找不到任何执行 `Output Assertions` 的程序；plugin-reviewer D9.2 只读 Trigger 两节做「和 description 是否对得上」的判断；唯一真正运行的是 Trigger 两节经 plugin-master iterate → skill-creator `run_eval.py` 的那条路径，而且只测是否触发。
- 维度相同，官方全部能运行：

| `eval.md` 的节 | 官方写法 |
|---|---|
| Trigger Tests | `tool_used` + `tool: Skill` + `input_match` |
| Negative Trigger Tests | 同上 + `min: 0, max: 0, arm: both` |
| Output Assertions | `regex` / `file_exists` / `tool_order` / `llm` |
| Redundancy Risk | `--ablation with-without` 自动算 Δ |

- 官方测不了的四类，`eval.md` 同样测不了（它什么都不跑）：跨插件调用、AskUserQuestion / 用户回复、Workflow 工具、依赖家目录 / 凭据 / 设备。
- skill-creator 保留：`run_loop` 做 description 优化；`run_eval.py:70-90` 在真实环境（继承环境变量、项目根目录、所有已装插件）里测触发竞争，这是官方隔离运行看不到的。它注册的是只含 description 的临时 command 文件（`:60-68`），不是 skill 正文。

## 实测记录

| # | 做了什么 | 看到什么 |
|---|---|---|
| 1 | 空目录里 `claude plugin eval init --bare demo` | `Error: … is not a plugin or skill folder — run … from the plugin's root folder, or pass --eval-dir`，exit 1 |
| 2 | 含 `.claude-plugin/plugin.json` 的目录里同一命令 | exit 0，生成 `evals/demo/prompt.md` + `graders/criteria.md` |
| 3 | `evals/skill-a/case-one/`、`evals/skill-b/case-two/` 各放一个带非法键的 `prompt.md` | 两个都被找到并报 `unknown frontmatter key`——两层嵌套可用 |
| 4 | 同一错误信息 | 列出允许的键：`schema_version, name, description, tags, plugins, runs, expected_outcome, model, max_turns, timeout_seconds, allowed_tools, artifact_publish, growthbook_overrides, append_system_prompt, env`，没有关联 skill 的键 |
| 5 | `evals/skill-a/` 只放 `NOTE.md`，另一个目录放一个坏用例 | 只报坏用例，`NOTE.md` 目录被忽略 |
| 6 | 只剩 `NOTE.md` 目录 | `No eval cases found under …` |
| 7 | 一个合法用例 + `--max-cost-usd 0` | `cost ceiling $0 hit; skipping remaining cases`，0 次运行，$0，exit 2 ——可以当加载校验 |
| 8 | `claude plugin eval skill-master --tag plugin-master --max-cost-usd 0` | `No eval cases found … under ~/.claude/plugins/cache/indie-toolkit/skill-master/1.2.0` ——裸名字解析到**已安装副本**，必须传路径 |
| 9 | `claude plugin eval ./skill-master --tag plugin-master --max-cost-usd 0` | `Ablation: 2 arms × 26 cases (156 runs)`，`cost ceiling $0 hit`，无加载错误 |
| 10 | 读 skill-creator `run_eval.py` | 读 `item["query"]`（`:204`、`:217`）；plugin-master 原来写的是 `"prompt"`，2026-09-12 已改 |

## 官方原文摘录

- 定位："`claude plugin eval` runs your plugin against a suite of test cases and scores the results." / "Use evals to measure how reliably your plugin steers Claude to the right outcome, to catch regressions …"
- 单位："Each case is a realistic prompt plus one or more graders." `init` "writes one case directory per prompt under `evals/`, each named after its prompt"。分组："one directory per case; nest under a non-case directory to group"
- 和 skill 的关联：「add a second grader that checks whether your skill is what produced the answer」，即 `tool_used` / `Skill` / `input_match`
- 隔离："Your user settings, hooks, `CLAUDE.md` files, MCP servers, other installed plugins, memory, and skills are absent"；"The case definitions are hidden from the agent. A run can't read the eval directory"
- Bash 沙箱："your home directory and Claude Code configuration are unreadable"，网络按域名授权
- Ablation 排除："Every `tool_used` grader whose `tool` is `Skill`" 与 `arm: with-only` 不计分；"Set `arm: both` … for a 'must not invoke the skill' check with `min: 0` and `max: 0`"
- 限流："each later run ends with that error, is graded on what it produced, and usually scores 0. The suite still finishes and isn't marked `partial`"

## 未验证

- AskUserQuestion 在 eval 运行里的表现（文档未提）
- Workflow 工具能否通过 `--allow-tools` 授权（文档可授权列表里没有）
- `plugins` 数组能否同时加载多个插件、用来测跨插件路由
- hook 注入的 `additionalContext` 是否出现在 `trace` 里

## 仓库现状（2026-09-12）

- 72 个 skill，51 个有 `eval.md`，22 个没有；51 个里 40 个写 `Last tested model: Opus 4.6`，37 个日期停在 2026-03-08。
- 旧决定 `docs/06-plans/2026-03-08-eval-infrastructure-phase2.md`：「co-located, not centralized」。本次改为插件级 `evals/<skill>/<case>/`，每个 skill 两边都存在，布局见 `eval-rules.md`。
- skill-master 是第一个按新规则落地的插件：`skill-master/evals/plugin-master/` 26 个用例（16 触发，其中一个带 intent-distiller 派发断言；9 不触发；1 个 slash 调用 insights 路由的首步断言）。

## plugin-master 首跑（2026-09-12）

`claude plugin eval ./skill-master --tag plugin-master --runs 1 --ablation none -j 2` · 26 cases · 421s · $5.03 · 被测模型 `claude-opus-5[1m]`（会话默认）

- **不触发 9/9 通过**：3 轮内都没调用 plugin-master。
- **触发 7/17 通过**，都是第一步就调用 Skill：`audit-my-plugin`、`auto-tune-skills-usage`、`bare-plugin-master`、`build-plugin-stale-prs`、`export-plugin-marketplace`、`propose-improvements-usage`、`run-insights-dev-workflow`。`build-plugin-stale-prs` 在 300s 超时，但 skill 触发和 intent-distiller 派发两条 grader 都通过。
- **9 条 3 轮内没触发**（逐条读过运行记录）：模型先自己动手——去找 prompt 里点名的东西（`commit`、`verify-plan`、`brainstorm`、`dev-workflow`，以及「this skill」「my other project」），或者直接写文件（`create-agent-validates-configs`、`create-skill-code-review`；后者的回复还提到沙箱里已有内置的 `code-review` skill）。3 轮上限下，这只证明「plugin-master 不是第一步」，不能证明「永远不触发」。`package-standalone-skill` 的运行记录已被清理，只知道 Skill 调用 0 次。
- **slash 用例是 grader 选错了**：用户输入的 `/plugin-master insights --window 30` 直接展开 skill，第一步就 Read 了 `skill-master/skills/plugin-master/insights.md`，Skill 工具调用为 0 → `tool_used: Skill` 看不到它。已改成 `slash-insights-reads-route-file`，断言第一步读 `insights.md`；规则见 `eval-rules.md`「Slash-typed prompts are not trigger cases」。
- 通过的用例 `NOTES` 里也有 `Reached maximum number of turns (3)`：skill 触发后继续执行、撞到上限，不影响判定。

## plugin-master 第二次运行（2026-09-12）

同一命令 · 26 cases · 377s · $5.73。与首跑相比改了两处：description 收窄「Not when」、移出路由摘要；首跑没触发的 9 条 `max_turns` 从 3 提到 10。两处同时改，而且每条只跑 1 次，所以哪条变化由哪处改动带来，**无法区分**。

- 不触发 9/9 通过；slash 改写后的 `slash-insights-reads-route-file` 通过（第一步读了 `insights.md`）。
- 触发 9/16 通过：比首跑多了 `create-skill-code-review` 和 `review-dev-workflow-plugin`。
- 7 条**跑完整轮都没触发**（`error` 为空，4–14 turns 自然结束，不再是撞轮数上限）：`commit-trigger-too-broad`、`create-agent-validates-configs`、`improve-trigger-quality`、`improve-verify-plan`、`inject-skill-other-project`、`iterate-brainstorm-skill`、`package-standalone-skill`。
- 这 7 条的运行记录已被清理（没有报错的运行不保留沙箱，要加 `--keep-temp`），HTML 报告里也没有最终回复，所以看不到模型最后做了什么。首跑的记录显示，这类 prompt 会让模型先去找它点名的东西（「this skill」「my commit skill」「verify-plan」），而空沙箱里这些东西都不存在。要分清是 description 抓不住，还是用例缺少现场，需要用 `scaffold_script` 放一个示例插件再跑。
- `improve-verify-plan` 得 0.5：`no-insights-route` 通过、`skill-fired` 失败。配对设计按预期生效——skill 没触发时，这个用例不会被负向 grader 空过。

## plugin-reviewer 真实运行（2026-09-12，契约验证）

用 general-purpose agent 读仓库里的新版 `plugin-reviewer.md` 执行（已安装的 `skill-master:plugin-reviewer` 仍是缓存里的 1.2.0 旧版）。它逐字引用了新的 9.2 标题和输入第 4 项；从用例收集到 16 条正向、9 条负向触发词，从 `eval.md` 收集到 0 条；四项布局检查通过。

另报出两个旧 bug，已修：`run_loop` 缺必填的 `--model`、`--skill-path` 传的是文件而不是目录（`run_loop.py:247/255/264`，本机两个已安装版本一致）；`--previous-workspace` 不是 `run_loop` 的参数，属于 `eval-viewer/generate_review.py`。

它的 L4（「默认两组对比下正向触发的回退测不出来」）被官方原文驳回：「If every grader in a case is one of these, they're scored normally instead」。只有同时带别的 grader 的用例（`build-plugin-stale-prs`），skill-fired 才会变成只作标记。

## 其他会话的发现

同日另一个会话建 `dev-workflow/evals/fix-bug/` 时记录在其 `FINDINGS.md`：`focus: trace` 的判分员看不到中间的编辑；`/<plugin>:<skill>` 开头会让对照组直接回 `Unknown command`、花费 $0，Δ 失真；Write / Edit 还要 `--allow-tools`。已并入 `eval-rules.md` 的 Grader pitfalls。
