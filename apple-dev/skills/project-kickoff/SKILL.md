---
name: project-kickoff
description: "Manual /project-kickoff only; not model-invocable. Runs the project kickoff flow to clarify requirements, converge scope, and produce execution recommendations. When the product's core value rests on measurement/inference accuracy, an efficacy claim, a state-of-the-art algorithm, or an established standard instrument, it also runs a domain-literature check (papers/DOI, benchmark pages) that can halt the flow if the mechanism is contradicted, and surfaces reusable mechanism-level implementations. Use when starting a new project on any platform (distinct from /write-dev-guide, which plans phased development after design is approved); iOS/macOS projects additionally receive Apple-native initialization (DesignSystem/ASC/CI-CD)."
disable-model-invocation: true
---

<!-- cost-posture: inherit (judgment/orchestration — 5 AskUserQuestion 检查点 + WebSearch 市场调研 + 2.5 领域研究检索（派 general-purpose，主线抽验一手来源）+ dispatch generate-design-prompt / generate-design-system / design-reviewer；多检查点编排，do-NOT-downgrade per project CLAUDE.md Skill Cost Posture 规则) -->

# Project Kickoff - 项目开题

新项目启动前的可行性分析和定位。

## 输入

用户描述项目想法。可以是模糊概念，如"做一个记账 App"。

## 流程

### 1. 需求澄清

如果输入不够明确，追问：
- 解决什么问题？
- 目标用户是谁？
- 有什么独特切入点？
- **目标平台**（iOS/macOS / Web / CLI / 跨端 / 其它）——决定后续是否走苹果原生初始化（DesignSystem/ASC/CI-CD）

直到形成清晰的项目概念。不清晰就不进入下一步。

### 2. AI 时代前置检验

在搜索竞品之前，先回答：

**是否需要开发？**
- 这个需求能否用现有 AI 工具直接解决？（ChatGPT、Claude、专用 AI 工具）
- 是否用 No-Code 工具组合就够了？（Notion、Airtable、Zapier）
- "做成 App"比"用现有工具"好在哪里？

**AI 替代风险**
- 如果 AI 能力继续提升，这个产品还有价值吗？
- 什么是 AI 难以替代的部分？

如果结论是"不需要开发"或"很快会被 AI 替代"，直接告诉用户，不继续往下走。

### 2.5 领域研究检索

查产品成立所依赖的**机制**在学术/工程文献里有没有验证结论、有没有现成实现、有没有更新的方向。

放在这个位置的理由：文献能证伪的是「这东西该不该存在」，与步骤 2 同一类问题。一旦证伪，必须在 CP2/CP3 的调研与规划投入之前开火。

#### 2.5.1 触发门（先判，四条全不中直接跳过）

此时还没有功能列表（那是步骤 6 的产物）。判据只用步骤 1 已经收到的三项——**解决的问题 / 目标用户 / 独特切入点**——看这个产品要成立，是否依赖下列之一：

1. **测量 / 推断的精度上限**（识别、评分、检测、预测）
2. **效果主张**（这个产品能改变行为 / 改善某个结果）
3. **有明确 state of the art 的算法**（调度、匹配、压缩、检索、排序）
4. **已存在的领域标准量表 / 工具 / 协议**

四条全不中 → 在 CP1 的「领域研究判定」行填「未触发（无机制依赖）」，并记下这一判，等步骤 8 创建 project-brief 时在其「领域研究」章节写一行「无机制依赖，跳过领域研究检索」。直接进入 CP1。**不要为了填充而硬找文献**——多数工具类项目（记账、待办、笔记）在这里正常跳过。

⚠️ **2.5 的任何产物在步骤 8 之前都不落盘**。project-brief 在步骤 8 才创建（且在 CP5 之后），而用户在 CP1 还能选「放弃」；本步只往 CP1 的展示位写，与 6.6.4 写「CP3 的平台 API 验证结果位置」同一范式。

这一判是粗判，只为拦住「核心机制不成立」这一类。功能级的复判在步骤 6：功能列表展开后冒出新的机制依赖，按第 6 步的第 3 条回补跑 2.5.2。

#### 2.5.2 提取机制清单

```
[机制依赖清单]
1. {机制} — 支撑 {什么功能} — 核心？是/否 — 如果它不成立：{产品还剩什么}
2. ...
```

「如果它不成立」这一栏不能空。填不出 = 它连机制都不是，从清单里删掉。

「核心？」栏决定 2.5.7 走哪条分支：**是** = 它不成立则产品不成立；**否** = 它不成立只是某个功能要换做法。两者的处理不同，别混。

**上限：最多 3 条核心机制**。超过 3 条时先向用户列出全部候选，让用户挑要查哪几条——不要自行扩表，每多一条就是一整轮 3 类查询加若干次抓取。

#### 2.5.3 检索

三类查询分开跑，别混：

| 类别 | 查询形状 | 找什么 |
|------|---------|--------|
| 机制有效性 | `{机制} efficacy` / `{机制} meta-analysis` / `{机制} randomized controlled trial` / `{中文领域词} 研究` | 这个机制到底成不成立、效应量多大 |
| 现成的轮子（机制层） | `{机制} algorithm implementation` / `{机制} library` / `{标准量表名} scoring` / `{任务} benchmark` | 别人已经写好的调度器 / 分析包 / 计分实现 |
| 前沿方向 | `{机制} survey {年份}` / `{机制} state of the art` | 有没有比原方案更新的做法 |

**每类查询取候选上限 5 条**，按来源优先级排序后取前 5；超出的不抓取、不进清单。

**与步骤 3 的边界**：步骤 3 的 `[产品类型] open source` 查的是**产品层**（有没有人做过同一个 App），本步查的是**机制层**（有没有人实现过这个算法/量表）。查询形状和来源都不同，两者不互相替代。

**与 6.6 的边界**：本步查**机制成不成立、精度上限多少**（文献与 benchmark）；6.6 查**该 API 在目标 target 能不能用、需要什么 Entitlement、有什么配额**（官方文档）。同一个 API 两步都会碰到时（如手写识别项目的 Vision / VNRecognizeTextRequest），**6.6 直接复用 2.5 的 `[可复用]` 条目与已抓页面，不重复检索**；本步也不去查 Entitlement 与配额，那是 6.6 的事。

**来源优先级**：期刊/会议论文摘要页（doi.org、arxiv.org/abs、pubmed.ncbi.nlm.nih.gov、ACM/IEEE DL）> 官方 benchmark 榜单与数据集主页 > 厂商技术报告 > 其它。

**零结果先验检索器，别当「无定论」**：某个机制三类查询全部零命中时，⛔ 不许写成「文献没有定论」——零结果同时兼容「确实没人研究过」和「我的关键词/工具坏了」，判别力为零。动作两步：① 换一次关键词重查 ② 在一个**已知有文献的邻近机制**上跑同一条查询，确认它能返回非零。正控通过后仍零命中 → 写「⚠️ 检索无命中」并注明查了哪些词，**不写「文献无定论」**；正控也返回零 → 检索器坏了，报给用户，本步结论全部作废。

#### 2.5.4 抓一手来源（硬门）

WebSearch 搜到的每一条，要进 project-brief 的结论，**必须先用 WebFetch 抓到它的摘要页并引用页面原文**。抓不到 → 该条标 ⚠️，只能当假说，不得写成结论，不得进入 CP1 的判定。

⛔ **禁止凭记忆补作者 / 年份 / 期刊 / DOI**。竞品链接点开就知真假，论文引用不是——作者+年份+期刊长得像可核验的东西，是这一步最强的编造载体。这条与 GATE「官方文档页先于一切」同口径：搜索摘要和博客解读等同「社区帖」，只能产「⚠️ 未证实」。

#### 2.5.5 可迁移性标注（逐条，缺这行的条目作废）

**适用范围**：✅、❌、⚠️无定论 三种状态的条目**逐条必写，缺则作废**。2.5.6 的 3b 三种（检索无命中 / 抓不到一手来源 / 一手来源抽验未通过）**不适用本节**——手上没有一手来源，没有可比对的机制，硬填就是编。

在适用范围内，每个引进来的数字 / 结论，写一行：

```
该数测的机制 = {X}，我手上的机制 = {Y}，判定：直接适用 / 仅作背景
```

两者不同 → 只能当背景，**不得用来支持或否定方案，不得当阈值依据**。写不出 X = 没读懂那个数，删掉该条。

最会骗人的形态是**同一模型家族、不同任务**：同一套 OCR 管线，印刷体 `cer_np` 0.0163、手写页 0.8950，差 55 倍。「它在文档解析榜上很强」说不了「它认得手写」。

#### 2.5.6 输出格式

```
[领域研究结果]
1. {机制} — 支撑 {功能} — 核心？是/否 — ✅ 有验证支持 — {结论一句话} — 来源：{摘要页 URL} — 迁移性：直接适用 / 仅作背景
2. {机制} — 支撑 {功能} — 核心？是/否 — ❌ 文献证伪 — {原文摘录} — 来源：{摘要页 URL} — 迁移性：直接适用 / 仅作背景
3a. {机制} — 支撑 {功能} — 核心？是/否 — ⚠️ 无定论 — {文献分歧一句话} — 来源：{摘要页 URL} — 迁移性：直接适用 / 仅作背景 — 建议 spike 验证
3b. {机制} — 支撑 {功能} — 核心？是/否 — ⚠️ 检索无命中 / 抓不到一手来源 / 一手来源抽验未通过 — 已查：{关键词与来源} — 建议 spike 验证
4. [可复用] {库/实现名} — {做什么} — {许可证} — 来源：{URL}
5. [新方向] {方向} — {与本项目的关系} — 来源：{URL}
```

⚠️ **迁移性字段的适用范围**：✅、❌、⚠️无定论（3a）三种**都必须填**，缺则按 2.5.5 作废。❌ 行比 ✅ 行更要紧——拿一份测了别的机制的研究去毙掉整个产品，正是 2.5.5 存在的理由。3b 那三种**不填也不作废**：手上根本没有一手来源，没有可比对的机制，硬填就是编。

**本块是行字段的唯一来源。** project-brief 的「机制验证」表写全 7 个字段（机制 / 支撑功能 / 核心 / 状态 / 结论 / 来源 / 迁移性）；CP1 的领域研究摘要表为控宽**只省 支撑功能 一列**，其余 6 个字段一一对应。除这一条明写的例外，两处都不自行增删字段。改这里就要同步改那两处。

#### 2.5.7 处理结果

格式与升级链沿用 6.6.3 的形状，但**分支不同**：6.6.3 的 ❌ 无条件停流程，本步按机制是否核心决定停不停。

⛔ **两件事分开判，不要合成一条链**：① **停不停流程**是整轮一个判定 ② **每条条目怎么处置**是逐条的，各条**并行适用、互不排斥**。上一版把两者写成互斥分支，结果是一条非核心 ❌ 会把同一轮里的核心 ⚠️ 挤掉。

**① 停流程判定（整轮一次）**

- **存在「❌ 且核心？是」的条目** → 停止流程，向用户报告该条的文献原文与来源，讨论替代机制或重新定位。调整后回 2.5.2 只为该机制重验。本轮其余条目留待重新定位后一并复议
- **否则** → 不停，进入 CP1

**② 逐条处置（对每一条独立执行，与 ① 无关）**

| 条目状态 | 处置 |
|---------|------|
| ✅ | 进 CP1 摘要表；按迁移性供步骤 5 / 6 / 6.5.7 使用 |
| ❌ 且核心 | 触发 ①；进 CP1 摘要表与 6.7 机制风险表 |
| ❌ 但非核心 | 进 CP1 摘要表与 6.7 机制风险表；步骤 6 规划该功能时换做法或列入「明确不做」 |
| ⚠️（四种子状态：无定论 / 检索无命中 / 抓不到一手来源 / 一手来源抽验未通过） | **逐条告知用户属于哪一种**，建议 spike 验证；进 CP1 摘要表、6.5.7 的「精度未知」设计规则、6.7 机制风险表。用户决定接受风险继续还是先验 |

⚠️ 同一轮里 ❌ 与 ⚠️ 并存是常态。**❌ 的存在不免除任何 ⚠️ 条目的处置**——尤其是核心机制的 ⚠️，那正是最需要 spike 的一条。

⚠️ **若本轮是步骤 6 第 3 条的回补**，不走本节，按步骤 6 那张返回契约表返回。

#### 2.5.8 执行方式与抽验

本步是 ≥2 次只读检索，按成本路由规则把 **2.5.3–2.5.6**（检索 + 抓取 + 标注 + 格式化）派给 **`general-purpose`** agent 执行。

**为什么指定 `general-purpose`**：本步要 WebSearch + WebFetch，且产出是判断型的（要判迁移性、要判核心与否）。不要用 `Explore`——它是代码检索形状的检索器，任务描述与工具用法都朝着「在仓库里定位代码」调，不适合外部文献的判断型抽取。

⛔ **派发提示词必须自包含，不许用节号指代。** 子代理没有本 SKILL.md，「按 2.5.6 格式」「2.5.4 的硬门」对它是悬空引用，结果是它自己发明查询形状和输出格式。主线在构造提示词时，把下列内容**逐字抄进提示词正文**：

1. 2.5.3 的三类查询表（含每类的查询形状）
2. 2.5.3 的候选上限（每类 5 条）、来源优先级列表、零结果先验检索器那一段
3. 2.5.4 的整段硬门（含禁止凭记忆补作者/年份/期刊/DOI 那句）
4. 2.5.5 的**整节**——模板行、判定规则（「两者不同 → 只能当背景，不得当阈值依据」）、删条规则（「写不出 X 就删掉该条」）。只给模板不给判据，等于让它填一个自己不懂的字段
5. 2.5.6 的输出格式块**及其下方两段 ⚠️ 说明**（迁移性对哪些状态必填、3b 为什么不填）
6. 本轮的机制依赖清单（把 2.5.2 的实际产物逐条粘进去，含「核心？」栏；不要写「见 2.5.2」）
7. **一条硬约束**：产物只作为文本返回，**不写任何文件**。project-brief 在步骤 8 才创建，此刻用户在 CP1 还能选「放弃」——`general-purpose` 有写权限，这条必须显式告诉它

**分工**：

- **agent 负责**：跑三类查询，对每条候选**自己 WebFetch 摘要页**，按抄给它的输出格式返回，每条带 URL + 页面原文摘录 + 迁移性行
- **主线负责**：收到后**自己 WebFetch 抽验 ≥2 条**它引用的摘要页，确认 URL 真实存在且原文支持所述结论

**抽验不过时**（上限写死，防死循环）：

- **第一次不过**：整批退回重跑一次，不做局部修补
- **第二次仍不过**：⛔ 不再重试。把该批全部条目降级为 ⚠️（注明「一手来源抽验未通过」），转 2.5.7 的分支 3 交用户决定

⚠️ 这道抽验不能省。开放式检索 + 判断型输出 + 无 ground truth，是编造风险最高的 agent 形态：它会把「查不到」转成「编得像」，产出语法通顺、来源格式完整、DOI 不存在的条目。主线对 agent 报告的抽验义务不可转嫁给用户。

### CP1: 项目概念确认

**展示内容**（2.5 触发时控制在 28 行内，未触发时 20 行内）：

| 维度 | 内容 |
|------|------|
| 项目名称 | {name} |
| 解决的问题 | {problem} |
| 目标用户 | {users} |
| 独特切入点 | {angle} |
| 目标平台 | iOS/macOS / Web / CLI / 跨端 / 其它（决定第 9 步是否执行苹果原生初始化） |
| AI 时代判定 | 值得开发 / 不需要开发 / AI 替代风险高 |
| AI 难以替代的部分 | {irreplaceable} |
| 领域研究判定 | 未触发（无机制依赖）/ 机制有验证支持 / 机制无定论 / **检索无命中（证据不足）** / 机制被证伪 |

> 判定行取**核心机制**的状态。一轮里核心与非核心结论不同时写成限定式，如「机制有验证支持（含 N 条非核心机制被证伪）」——不要用非核心的 ❌ 去写整行，那会读成产品的核心已经死了。

**领域研究摘要**（仅 2.5 触发时显示，控制在 6 行内；未触发时整块省略）。字段按 2.5.6 渲染，CP1 为控宽只省 支撑功能 一列，其余不自行增删：

| 机制 | 核心 | 状态 | 结论 | 来源 | 迁移性 |
|------|------|------|------|------|--------|
| {mechanism} | 是/否 | ✅/❌/⚠️ | {one-line} | {URL} | 直接适用 / 仅作背景 |

**6 行怎么分**：表头 2 行 + 条目最多 3 行 + 可复用 1 行。条目超过 3 条时，**优先列全部核心机制与全部 ❌ 条目**，其余合并为一行「其余 N 条 ✅，详见 project-brief」。project-brief 的机制验证表不受此限，写全。

可复用实现：{名称 + 许可证 + URL}，无则写「无」。

> **平台判定口径**：`platform==apple` 指 iOS / iPadOS / macOS / watchOS / tvOS 任一（Apple 生态原生项目）；其余（Web / CLI / 跨端 / 后端 / 其它）置 `platform==other`，跳过苹果专属子步（DesignSystem.swift / ASC / CI-CD），保留通用 docs 骨架（CLAUDE.md / AI-CONTEXT / README / Notion / GitHub Issue）。

**[Expectation Recap]** (用人话给用户复述一遍，避免表格化沟通)

用一句话告诉用户：「我这边理解你的项目是 {one-sentence project summary}，主要解决 {problem in user's words}，AI 时代评估结论是 {verdict}。{2.5 触发时补一句：这个产品靠 {mechanism} 成立，文献查下来 {✅ 有验证支持 / ⚠️ 没有定论 / ❌ 被证伪}，{一句话说这对方案意味着什么}；未触发时补：这个项目不依赖需要查文献的机制，跳过了领域研究。}下一步我打算 {next step}。」
再问：「这样理解对吗? 如果框架就不对，我们停下来重新澄清；如果是细节调整，回答下面的选项。」

**询问用户**（使用 AskUserQuestion）：

> 以上是项目概念和 AI 时代可行性判定。
>
> - **继续** — 进入市场调研
> - **定制项目** — 客户已确认需求，跳过市场调研，直接进入功能规划
> - **调整** — 修改概念或切入点后重新评估
> - **放弃** — 终止开题流程

等待用户回复。选择「调整」则回到步骤 1 重新澄清需求；选择「放弃」则终止流程。

选择「定制项目」时：
- **步骤 2.5（领域研究检索）照常执行**——机制成不成立与客户是否确认需求无关；客户确认的是「要什么」，文献回答的是「这东西做不做得出来 / 有没有效」。它位于 CP1 之前，本分支不影响它
- 跳过步骤 3（市场调研）、4（竞品分析）、5（定位分析）、CP2
- 直接进入步骤 6（功能规划）
- 步骤 2 的 AI 时代前置检验调整为：不问「是否需要开发」（客户已确认），保留「AI 能力评估」（帮客户识别哪些功能可用 AI 更高效地做）
- project-brief.md 中「市场调研」章节写入：「定制项目，客户已确认需求，跳过市场调研」
- 后续步骤中涉及「差异化」「护城河」「竞品」的分析内容，替换为客户需求对齐分析

### 3. 市场调研

使用 WebSearch 搜索相关产品：

**搜索来源**：
- GitHub：开源实现、技术方案
- Product Hunt：已发布产品、用户反馈
- App Store / Google Play：移动应用评分评论
- IndieHackers / HackerNews：独立开发者经验
- 通用搜索：测评文章、对比分析

**搜索策略**：
- `[产品类型]` 直接搜索
- `[产品类型] alternatives` 竞品列表
- `[产品类型] open source` 开源方案
- `[用户痛点]` 从问题角度搜索

每个来源至少搜索一次，汇总 5-10 个主要竞品。

**与 2.5 的边界**：本步只查**产品层**——谁做过同一个 App、卖点是什么、用户抱怨什么。**机制层**的检索（某个算法的现成实现、某个量表的计分代码、某个机制的有效性证据）归步骤 2.5，不在本步重复。如果 2.5 已产出 `[可复用]` 条目，本步不再为同一个机制搜第二遍。

### 4. 竞品分析

对每个竞品整理：

| 维度 | 内容 |
|------|------|
| 产品名称 | 名称 + 链接 |
| 核心功能 | 主要卖点 |
| 目标用户 | 面向谁 |
| 商业模式 | 免费/付费/订阅 |
| 优点 | 做得好的地方 |
| 缺点 | 用户抱怨的点 |
| 技术栈 | 如果是开源项目 |

### CP2: 差异化方向确认

**展示内容**（控制在 40 行内）：

**竞品概览**：

| 竞品 | 定位 | 商业模式 | 优点 | 缺点 |
|------|------|---------|------|------|
| {name1} | {positioning} | {model} | {strength} | {weakness} |
| ... | ... | ... | ... | ... |

**关键发现**（3 条以内）：

1. {finding1}
2. {finding2}
3. {finding3}

**推荐差异化方向**：{direction}

**[Expectation Recap]**

告诉用户：「调研下来 {N} 个竞品，主要矛盾是 {one-line summary of competitive landscape}，我建议你的差异化点是 {direction in user's words}。如果按这个方向走，你需要在 {key area} 上比竞品做得明显更好。」
再问：「这个差异化方向你认吗? 觉得不对的话，告诉我哪里没抓住。」

**询问用户**（使用 AskUserQuestion）：

> 以上是竞品分析和推荐的差异化方向。
>
> - **确认方向** — 按此方向进入定位分析和功能规划
> - **调整方向** — 指定不同的差异化方向
> - **补充调研** — 补充特定竞品或来源的调研

等待用户回复。选择「调整方向」则根据用户指定的方向重新分析；选择「补充调研」则回到步骤 3 补充搜索。

### 5. 定位分析

基于调研结果，分析：

- **差异点**：与竞品的核心区别
- **护城河**：难以被复制的优势（特别关注数据护城河）
- **风险点**：潜在挑战和应对思路
- **市场机会**：为什么现在做这个

**引用 2.5 结论时的要求**：把「机制已被验证」写进护城河或市场机会，必须同时给出该条的**摘要页 URL** 和**迁移性判定**。标为「仅作背景」的条目不能承重——它证明不了你这个场景，只能作为叙述背景。2.5 的 `[新方向]` 条目属于市场机会的候选来源，同样带 URL。

如果调研后发现"这个方向已经很卷，没有明显差异化空间"，直接告诉用户，不要硬凑。

### 6. 功能规划

- **完整功能列表**：要做的所有功能（不是 MVP，是完整版）
- **明确不做**：边界在哪里
- **技术选型**：推荐技术栈和理由
- **数据策略**：产品如何积累独特数据

**与 2.5 的连接**（三条）：

1. **参数与阈值优先引用文献**：功能涉及具体数值（间隔、阈值、周期、评分权重、目标值）时，如果 2.5 有「直接适用」的结论，用它并附来源；没有则该值标注「拍脑袋默认值，待 spike 验证」，不要写得像有依据。
2. **技术选型优先复用 2.5 的 `[可复用]` 条目**：已有成熟实现的机制不自己重写，选型表的「理由」栏写清为什么用它或为什么不用。
3. **新出现的机制依赖回补**：如果功能规划展开后冒出 2.5 当时没识别到的机制依赖（触发门四条之一），回到 2.5.2 只为这一项补跑检索（2.5.2 → 2.5.6），结论并入原清单。

   ⛔ **回补有独立的返回契约，不走 2.5.7**——2.5.7 的出口写的是「进入 CP1」，那会把你送回一个已经确认过的检查点（非定制项目还要连 CP2 一起重跑）。回补按下表返回：

   | 补跑结果 | 动作 | 回到哪 |
   |---------|------|--------|
   | ✅ | 并入原清单，按本节第 1、2 条使用 | 步骤 6 继续，**不回 CP1/CP2** |
   | ⚠️ | 并入原清单，该功能按 6.5.7 的「精度未知」设计，条目进 6.7 机制风险表 | 步骤 6 继续，**不回 CP1/CP2** |
   | ❌ 且核心 | 停下，向用户报告文献原文与来源，**调整功能列表**（不是调整项目概念），只为该机制重跑 2.5.3–2.5.6 | 调整后回步骤 6，**不回 CP1/CP2** |
   | ❌ 但非核心 | 该功能换做法或列入「明确不做」，条目进 6.7 机制风险表 | 步骤 6 继续 |

### 6.5 AI Native 架构评估

如果项目涉及 AI 能力，评估 AI Native 架构需求：

#### 6.5.1 AI 集成深度

| 级别 | 描述 | 架构需求 |
|------|------|---------|
| **Level 0** | 无 AI | 跳过本章节 |
| **Level 1** | AI 辅助 | 单向 API 调用，无需 Agent |
| **Level 2** | AI 增强 | 需要 Tool Calling + 简单 Agent |
| **Level 3** | AI 原生 | 完整 Agent 框架 + 多 Tool + 上下文管理 |

#### 6.5.2 Tool-First 设计检查

如果 Level >= 2，评估：

- [ ] **Service 可 Tool 化**：现有 Service 能否暴露为 AI Tool？
- [ ] **Tool Schema 设计**：Tool 输入输出是否清晰、可验证？
- [ ] **幂等性**：Tool 是否幂等（可安全重试）？
- [ ] **权限控制**：敏感 Tool 是否需要用户确认？

#### 6.5.3 Agent 策略选择

| 策略 | 适用场景 | 复杂度 |
|------|---------|-------|
| **Simple** | 单次 Tool 调用 | 低 |
| **ReAct** | 多步推理、需要观察 Tool 结果 | 中 |
| **CoT** | 需要展示推理过程 | 中 |
| **Multi-Agent** | 复杂任务分解、专家协作 | 高 |

#### 6.5.4 上下文管理需求

- [ ] **对话历史**：是否需要跨消息上下文？
- [ ] **用户偏好学习**：是否需要长期记忆？
- [ ] **Token 预算**：如何处理超长对话？

#### 6.5.5 可观测性规划

- [ ] **Tracing**：是否需要完整调用链追踪？
- [ ] **Metrics**：需要监控哪些指标（Token、延迟、成本）？
- [ ] **Audit**：是否有合规审计需求？

#### 6.5.6 错误恢复策略

- Tool 执行失败如何处理？
- LLM 调用超时如何处理？
- 如何避免无限循环？

#### 6.5.7 AI 推断功能设计原则

如果项目功能涉及机器推断/分析（智能分类、自动标签、行为预测等），设计时遵守：

- **宁漏勿误**：阈值宁严勿松，错误推断比没有推断更糟
- **明确告知**：UI 中标注这是机器推断，不是确定结果
- **保留覆盖入口**：用户能修正机器判断
- **精度上限以 2.5 的 ✅ 条目为准**：设计推断功能的准确率预期时，只认 2.5 中标为「直接适用」的数字。标为「仅作背景」的数字**不得当作阈值或准确率依据**——它测的是另一个机制，拿来定阈值等于把别人任务的难度当成自己的。2.5 里该机制是 ⚠️（无定论）时，功能按「精度未知」设计：先做人工确认流程，不做自动执行。

#### 6.5.8 架构原型决策

在确定 AI 集成深度后，判断项目属于哪个架构原型：

| 原型 | 描述 | 典型特征 | 推荐技术栈 |
|------|------|---------|-----------|
| **Simple Skill** | 单命令完成单任务 | 无状态、单次输入输出、无 UI | Claude Code skill / CLI |
| **Multi-Skill Workflow** | 多步骤编排、有状态流转 | 步骤间依赖、需要上下文传递 | Agent + Tool chain |
| **Content Studio** | 内容生产/编辑为核心 | 需要预览、迭代、版本管理 | UI + AI backend |
| **Data + MCP Tool** | 数据查询/操作为核心 | 外部数据源集成、结构化输出 | MCP server + Tool schema |

**判定流程**：
1. 用户需求可以用一句话 prompt 完成 → Simple Skill
2. 需要多步骤但不需要 UI → Multi-Skill Workflow
3. 核心价值是内容创建/编辑 → Content Studio
4. 核心价值是连接/查询外部数据 → Data + MCP Tool
5. 混合型：列出主原型 + 辅原型，主原型决定架构骨架

#### 6.5.9 Terminal-First 默认检查

在决定构建 UI 之前，回答：

- [ ] **这个功能必须有 UI 吗？** 如果 terminal 命令 + 文本输出就能满足 80% 的使用场景，先做 CLI 版本
- [ ] **UI 的不可替代价值是什么？** 列出 terminal 无法提供的具体能力（实时预览、拖拽操作、可视化图表等）
- [ ] **成本对比**：CLI 开发量 vs UI 开发量，维护成本差异

如果无法列出 UI 的不可替代价值 → 先做 CLI，用户反馈确认需要 UI 后再加。

#### 6.5.10 三次法则（Three Times Rule）

评估自动化时机：

- 第一次手动做 → 记录过程
- 第二次手动做 → 提取模式，写成文档
- 第三次手动做 → 自动化

在 MVP 规划中标记哪些功能适用三次法则：先手动/半自动验证价值，再投入自动化开发。避免过早自动化尚未验证的流程。

#### 6.5.11 AI 反模式目录

检查项目设计是否包含以下反模式：

| 反模式 | 检测信号 | 问题 | 替代方案 |
|--------|---------|------|---------|
| **Prompt Spaghetti** | 单个 prompt > 2000 字，混合多种指令 | 不可维护、难以调试 | 拆分为多个 skill，每个 < 500 字 |
| **God Agent** | 一个 agent 处理所有任务 | 上下文污染、精度下降 | 按职责拆分专用 agent |
| **Invisible AI** | AI 做了决策但用户看不到推理过程 | 信任问题、调试困难 | 输出推理链、标注置信度 |
| **Token Waste Loop** | 每次调用传递完整历史 | 成本高、延迟大 | 摘要压缩、选择性上下文 |
| **Hallucination Amplifier** | AI 输出直接作为下一步 AI 输入 | 错误级联放大 | 中间加验证/人工检查点 |
| **UI-First Trap** | 先做 UI 再考虑 AI 能力边界 | UI 承诺了 AI 做不到的事 | 先验证 AI 能力，再设计 UI |

对每个匹配的反模式，在 project-brief 中记录缓解措施。

### 6.6 平台 API 可行性验证

在确认功能范围之前，验证架构依赖的关键平台 API 和能力是否真的能按设计方式使用。

**平台门控**：
- `platform==apple`：走 6.6.1–6.6.3 Apple 专属路径（查 Apple Developer 文档、Entitlement、Extension 限制），与改前行为一致。
- `platform==other`：走 6.6.4 通用平台 / 第三方 API 可行性核查；无关键外部依赖时精简带过（一句话说明 + 跳过子步）。

#### 6.6.1 提取关键依赖

**`platform==apple`（iOS/macOS）；非苹果项目跳过本子步（由 6.6.4 取代）。**

**与 2.5 的边界**：2.5 已经回答过「这个机制成不成立、精度上限多少」（文献层）。本步只问「该 API 在目标 target 能不能用、需要什么 Entitlement、有什么限制」（官方文档层）。同一个 API 两步都碰到时，**直接复用 2.5 的 `[可复用]` 条目与已抓页面**，不重复检索，也不重新判断它的精度。

从步骤 6 的功能列表和技术选型中，列出架构成立所依赖的关键 API/能力点。重点关注：

- **跨 target 数据流**：Extension ↔ Main App、Widget ↔ Main App 之间传递的每种数据类型
- **受限框架**：HealthKit、CallKit、Messages、SMS、Push Notification、NFC 等 Apple 管控较严的框架
- **需要特殊 Entitlement 的能力**：App Groups、Keychain Sharing、Associated Domains 等
- **Extension 中使用的 API**：Extension 对可用 API 有独立限制

输出格式：

```
[关键依赖清单]
1. {API/能力} — 用于 {什么功能} — 架构中的角色：{做什么}
2. ...
```

#### 6.6.2 逐项查官方文档验证

**`platform==apple`；非苹果项目跳过本子步（由 6.6.4 取代）。**

对清单中每一项，用 WebFetch 访问 Apple Developer Documentation 对应页面，确认：

- 该 API 在目标 target 类型中是否可用
- 数据是否允许在设计的路径上流转（特别是跨进程/跨 target）
- 有无明确的使用限制或禁止事项
- 需要哪些 Entitlement，Entitlement 是否对个人/组织开发者开放

**搜索策略**：
- 直接访问框架文档页：`https://developer.apple.com/documentation/{框架名}`
- 访问对应 Extension 类型的文档：`https://developer.apple.com/documentation/{extension类型}`
- 如果文档中未明确说明限制，补充搜索：WebSearch `"{API名}" "{Extension类型}" restrictions site:developer.apple.com`

输出格式：

```
[API 验证结果]
1. {API/能力} — ✅ 可行 — 文档确认：{关键原文摘录}
2. {API/能力} — ❌ 不可行 — 文档原文：{限制描述} — 来源：{URL}
3. {API/能力} — ⚠️ 文档未明确 — 需要 spike 验证
```

#### 6.6.3 处理验证结果

- **全部 ✅**：进入 CP3
- **有 ❌**：停止流程，向用户报告硬限制，讨论替代架构方案。调整架构后重新从 6.6.1 验证
- **有 ⚠️**：告知用户哪些点文档未明确，建议在正式开发前用最小工程 spike 验证。用户决定是否现在验证还是接受风险继续

#### 6.6.4 通用平台 / 第三方 API 可行性核查（非 iOS 路径）

**仅 `platform==other`（Web / CLI / 跨端 / 后端 / 其它）。** iOS 项目走 6.6.1–6.6.3，**跳过本子步**（与改前行为一致）。

**目标**：验证架构依赖的关键平台 API、第三方服务、运行环境能力真的能按设计方式使用。这与 6.6 的立意完全一致，只是把 Apple 专属路径换成目标平台的中性路径。

**步骤 A — 提取关键依赖**：

从步骤 6 的功能列表和技术选型中，列出架构成立所依赖的关键能力点。重点关注：

- **目标平台 SDK / 浏览器 API / CLI runtime**：核心依赖是否在目标平台存在、版本要求
- **第三方服务**：云函数、数据库、身份认证、支付、推送、邮件等的 API 限额 / 鉴权 / 速率 / 条款
- **外部数据源**：官方 API、爬虫数据、付费数据的接入条件与限制
- **跨进程 / 跨服务调用**：数据是否允许在设计的路径上流转（如 webhook 鉴权、CORS、message queue 等）

**判断无外部依赖**：如果项目纯前端 / 纯本地 CLI / 无第三方 API / 无外部数据源，则本子步精简带过——在 CP3 的「平台 API 验证结果」位置写一行「无关键外部 API 依赖，跳过核查」，直接进入 CP3。

**步骤 B — 逐项查官方文档验证**：

**与 2.5 的边界**（与 6.6.1 同口径，本路径同样适用）：同一个 API/服务如果 2.5 已经抓过页面，**直接复用 2.5 的 `[可复用]` 条目与已抓页面**，本步只补查配额 / 鉴权 / 速率 / 计费条款，不重复检索，也不重新判断它的精度。

对清单中每一项，用 WebFetch 访问目标平台/服务的官方文档页面，确认：

- 该 API/服务在目标平台上是否可用（浏览器版本、runtime 版本、SDK 版本要求）
- 数据是否允许在设计的路径上流转（鉴权、CORS、scoping）
- 有无明确的使用限制、配额、速率
- 计费条款：是否有免费额度、是否需要提前申请、商业使用限制

**搜索策略**：
- 直接访问 SDK/服务文档首页 + 关键 API 详情页
- 必要时补充搜索：`WebSearch "{api名} rate limit" "{api名} authentication"` 等
- 对 LLM / AI 服务的模型 API：必须验证 organization 是否已开通该模型、调用额度、地区限制

输出格式：

```
[API 验证结果]
1. {API/能力} — ✅ 可行 — 文档确认：{关键原文摘录}
2. {API/能力} — ❌ 不可行 — 文档原文：{限制描述} — 来源：{URL}
3. {API/能力} — ⚠️ 文档未明确 — 需要 spike 验证
```

**步骤 C — 处理验证结果**（与 6.6.3 同口径）：

- **全部 ✅**：进入 CP3
- **有 ❌**：停止流程，向用户报告硬限制，讨论替代架构方案。调整架构后重新从 6.6.4 步骤 A 验证
- **有 ⚠️**：告知用户哪些点文档未明确，建议在正式开发前用最小工程 spike 验证。用户决定是否现在验证还是接受风险继续

### 6.7 事前验尸（Pre-mortem）

假设项目已上线 6 个月后失败。从以下维度推演最可能的失败原因：

**推演维度**：

- **技术风险**：架构假设不成立、关键 API 限制未发现、性能瓶颈、平台版本兼容性
- **机制风险**：机制被文献证伪或无验证支持——**核心与非核心都算**，2.5 中标 ❌/⚠️ 的条目逐条进本表（非核心 ❌ 不停流程，但风险要留痕）；另含拿「仅作背景」的数字定了阈值、依赖的现成实现许可证不允许商用
- **产品风险**：用户不买账、需求理解偏差、核心体验不够好、竞品先行（定制项目跳过竞品相关）
- **执行风险**：范围蔓延、关键路径单点依赖、独立开发者精力分配、技术债累积
- **数据风险**：冷启动问题、数据质量不可控、隐私合规障碍

**输出格式**：

| 失败场景 | 维度 | 可能性 | 影响 | 缓解措施 | 计划应覆盖 |
|----------|------|--------|------|----------|-----------|
| {scenario} | 技术/机制/产品/执行/数据 | 高/中/低 | 致命/严重/可控 | {mitigation} | ✅ 写入 dev-guide / ⚠️ 需 spike 验证 |

**处理规则**：

- 可能性「高」+ 影响「致命」或「严重」的项：必须在 project-brief.md 的「风险与缓解」章节记录，且标记「计划应覆盖」= ✅ 的条目传递给后续 `/write-dev-guide`
- 如果发现致命级风险且无可行缓解措施：暂停流程，向用户报告风险详情，询问是否继续
- 定制项目：跳过「竞品先行」相关风险项

### CP3: 功能范围确认

**展示内容**（控制在 60 行内）：

**产品定位摘要**：

- 差异点：{differentiation}
- 护城河：{moat}
- 目标用户：{users}

**功能列表**：

| 功能 | 描述 | 优先级 |
|------|------|--------|
| {feature1} | {desc} | 核心 |
| {feature2} | {desc} | 核心 |
| ... | ... | ... |

**明确不做**：

- {not_doing_1}
- {not_doing_2}

**技术选型**：

| 技术 | 选择 | 理由 |
|------|------|------|
| {category} | {choice} | {reason} |

**AI Native 级别**：Level {N} — {description}

**平台 API 验证结果**：

- `platform==apple`：显示下表（来自 6.6.1/6.6.2）
- `platform==other`：仅在 6.6.4 标记有外部依赖时显示精简表（来自 6.6.4）；无外部依赖时此段写「无关键外部 API 依赖，跳过核查」

| API/能力 | 用途 | 状态 | 说明 |
|----------|------|------|------|
| {api1} | {usage} | ✅/❌/⚠️ | {detail} |
| ... | ... | ... | ... |

**关键风险（事前验尸）**：

仅列出可能性「高」且影响「致命」或「严重」的条目：

| 失败场景 | 缓解措施 | 计划应覆盖 |
|----------|----------|-----------|
| {scenario} | {mitigation} | ✅/⚠️ |

**[Expectation Recap]**

告诉用户：「定位是 {differentiation in 1 sentence}，会做 {N} 个核心功能，明确不做 {M} 个相邻功能，技术上选了 {tech stack one-line}，关键风险是 {top risk}。开发完成后用户应该能 {one-sentence user outcome}。」
再问：「这个范围你认吗? 任何一项不对，告诉我具体是哪个。」

**询问用户**（使用 AskUserQuestion）：

> 以上是产品定位、功能范围、技术选型、AI 集成评估、平台 API 验证和关键风险。
>
> - **确认范围** — 按此范围进入设计生成
> - **调整功能** — 增删功能或调整优先级
> - **调整技术选型** — 修改技术方案

等待用户回复。选择「调整功能」或「调整技术选型」则修改后重新展示本检查点。

### 7. 设计生成

基于步骤 1-6 的分析结果，生成 UI 设计稿（平台感知）。

**平台门控**：
- `platform==apple`：调用 `dev-workflow:generate-design-prompt` skill（参数 `all`，跨插件调用；该 skill 自动检测 iOS 平台并输出 Stitch prompt）为项目生成主界面及各屏幕的 Stitch prompt。
- `platform==other`：调同一个 skill（`generate-design-prompt` 跨插件不感知平台，按项目的设计目标工具——Stitch for Web / Figma / 其他——输出对应 prompt）。调用方式与参数与 iOS 路径一致（不改 cross-plugin 调用契约）。

1. 调用 `dev-workflow:generate-design-prompt` skill 为项目生成主界面及各屏幕的设计 prompt（按目标平台走对应输出格式）
2. 对每个包含列表/内容区域的屏幕，标记需要空状态设计。空状态是新用户首次看到的界面，优先级不低于填充态
3. 从 skill 输出中提取：屏幕清单（名称 + 功能一句话）、每个屏幕的核心 UI 区域列表、需要空状态的屏幕标记
4. 将提取结果填入 CP4 展示模板

### CP4: 视觉方向确认

**展示内容**（控制在 40 行内）：

**屏幕清单**：

| 屏幕 | 功能 | 核心 UI 区域 | 空状态 |
|------|------|-------------|--------|
| {screen1} | {function} | {zones} | 需要 / — |
| {screen2} | {function} | {zones} | 需要 / — |
| ... | ... | ... | ... |

**Stitch prompt 数量**：主 prompt 1 条 + follow-up {N} 条

**[Expectation Recap]**

告诉用户：「设计 prompt 已经按你的产品逻辑生成了 {N} 个屏幕，覆盖 {key flows in user's words}。接下来你要么用目标设计工具出图（`platform==apple` 走 Stitch；`platform==other` 走 Stitch for Web / Figma / 其他），要么提供已有设计稿，要么先跳过设计直接开发。」
再问：「这几个屏幕的覆盖范围你认吗? 如果还差关键屏幕，告诉我补哪个。」

**询问用户**（使用 AskUserQuestion）：

> Stitch prompt 已生成。选择后续方式：
>
> - **用 Stitch 生成设计** — 将 prompt 粘贴到 Stitch 生成 UI，完成后提供设计文件路径继续流程
> - **已有设计稿** — 提供设计文件目录路径
> - **跳过设计** — 不使用设计稿，后续使用默认 Design System 值

等待用户回复。选择「用 Stitch 生成设计」则暂停流程，用户在 Stitch 中完成设计后回来提供文件路径；选择「已有设计稿」则记录路径；选择「跳过设计」则标记无设计输入，跳过 7.5，直接进入 CP5。设计文件路径将在步骤 7.5 和 9.6 中使用。

### 7.5 设计评审

**前置条件**：CP4 中用户提供了设计文件目录路径。如果选择了「跳过设计」，跳过本步。

读取设计目录下的全部文件，以顶尖视觉设计师视角完成评审。

**平台门控**：
- `platform==apple`：iOS 分支——保留 7.5.0 Source of Truth 标定（写 `design-rules.md` 喂 `apple-dev:design-reviewer`、`component-styles.md` 供 plan-writer）；逐屏点评 / 跨屏一致性 / 生成 REVIEW.md 均按现状执行（与改前一致）。
- `platform==other`：非 iOS 分支——**跳过 7.5.0 Source of Truth 标定**（不写 `design-rules.md` 给 apple-dev reviewer；不写 `component-styles.md` 用于 Swift token；该 reviewer 是 iOS 耦合）。其余子步（7.5.1 逐屏点评 / 7.5.2 跨屏一致性 / 7.5.3 生成 REVIEW.md / 7.5.4 用户确认）通用视觉评审对所有平台都执行——产 REVIEW.md 供后续开发对照。如果设计格式恰好是 Stitch DESIGN.md，仍可识别 sections 写入 `docs/02-architecture/design-source.md`（format / 路径 / sections 记录与 iOS 同），仅不抄录到 `design-rules.md` / `component-styles.md`。

**文件类型处理**（按识别优先级）：
- **Stitch DESIGN.md（9 节标准格式）**：顶层 `DESIGN.md` 包含 Visual Theme / Color Palette / Typography / Component Stylings / Layout / Depth 等 section（≥6 个匹配 = 判定为 Stitch 格式）。直接从 section 表格读取语义化 token，结论引用 `DESIGN.md § N` 而非数值。Read `references/doc-templates.md` 的「DESIGN.md (Stitch 9-section) 识别」段执行结构化识别。
- **W3C DTCG `tokens.json` / `design-tokens.json`**：解析 JSON token tree，结论引用 `tokens.json#path/to/value`
- **HTML/CSS + 自定义 design-spec.md**：可读取精确的间距、颜色、字体值，评审结论引用具体数值
- **纯图片（PNG/JPG/PDF）**：只能做视觉观察，间距和颜色值标注为 `~近似值`，不做精确度量声称
- 优先级：Stitch DESIGN.md > DTCG JSON > HTML/CSS + Markdown > 图片

#### 7.5.0 Source of Truth 标定

如果识别到 Stitch DESIGN.md：

1. 在 `docs/02-architecture/design-source.md` 写入：format、绝对路径、识别到的 sections、识别日期（参考 `references/doc-templates.md`「DESIGN.md (Stitch 9-section) 识别」段的模板）
2. 把 DESIGN.md 中 section 7（Do's and Don'ts）和 section 9（Agent Prompt Guide）的内容 verbatim 抄到 `docs/02-architecture/design-rules.md`，作为后续 apple-dev:design-reviewer / apple-dev:ui-reviewer agent（通过 /review-execution 派发）的判据来源
3. 把 section 4（Component Stylings）抄到 `docs/02-architecture/component-styles.md`，供 plan-writer 实现各组件时引用

如果未识别到 Stitch DESIGN.md：跳过本步，按原文件类型处理逻辑评审。

#### 7.5.1 逐屏点评

对每个屏幕/页面评价：

- **评级**：✅✅ 最佳 / ✅ 优 / ➖ 可用但有瑕疵 / ⚠️ 需调整
- **信息层次**：内容组织是否清晰、扫一眼能否抓到重点
- **交互合理性**：操作入口是否明确、操作流是否顺畅
- **视觉细节**：间距、颜色、对比度、一致性
- **亮点**：值得保留的设计决策
- **问题**：需要在实现中修正或调整的点

#### 7.5.2 跨屏一致性检查

检查全部屏幕之间的一致性问题：

| 检查维度 | 说明 |
|----------|------|
| 色彩一致性 | 同一 token 在不同屏幕上是否一致 |
| 导航风格 | 标题位置、返回按钮、tab bar 在各屏幕是否统一 |
| 组件风格 | 按钮、卡片、列表项等在各屏幕是否一致 |
| 间距节奏 | 各屏幕的间距系统是否统一 |
| 图标风格 | 线条粗细、填充风格、尺寸是否一致 |

#### 7.5.3 生成 REVIEW.md

在设计文件目录下创建 `REVIEW.md`，结构如下：

```markdown
# {项目名} Design Review

> 评审日期：{date}
> 目的：记录设计稿已知问题和刻意偏离，供后续开发对照。
> 规则：如果 UI 实现与设计稿不一致，先查本文档。在此列出的 = 已知偏差，不是 bug。

## 整体评价

{一段话总结}

---

## 已知问题（实现时需修正）

### P{N} — {问题标题}
- **位置**：{屏幕名}
- **问题**：{描述}
- **处理**：{实现时如何修正}

---

## 刻意不采纳的设计元素

### D{N} — {元素标题}
- **位置**：{屏幕名}
- **设计稿**：{设计稿中的做法}
- **不采纳原因**：{为什么不用}
- **决策人**：产品评审 / 工程评审

---

## 采纳且需要重点保留的设计亮点

| 编号 | 位置 | 亮点 | 说明 |
|------|------|------|------|
| H{N} | {屏幕名} | {亮点描述} | {为什么必须保留} |
```

**P 条目来源**：Stitch/工具限制导致的问题（如 Web 字体、静态图片替代相机）、跨屏一致性问题、对比度/间距等视觉问题。

**D 条目来源**：设计稿中的做法与 iOS 平台惯例冲突、与 Apple HIG 不协调、增加维护成本但收益不明确。每条必须写明不采纳原因，让后续开发者理解这是刻意决策而非遗漏。

**H 条目来源**：体现产品核心逻辑的 UI 细节、解决真实用户矛盾的交互方案、有辨识度的视觉设计。这些是实现时不能丢失的设计意图。

**空 section 处理**：如果某个 section 没有条目，在 section 标题下写 `无`。不要为了填充而发明问题。

#### 7.5.4 用户确认

**D 条目需逐条确认**：D 条目是 AI 判断的"不采纳"建议，用户可能有不同意见。在 AskUserQuestion 中逐条列出 D 项摘要，让用户明确知道哪些设计元素将被跳过。

**询问用户**（使用 AskUserQuestion）：

> 设计评审完成，REVIEW.md 已创建。
>
> 以下设计元素建议不采纳：
> - D1: {摘要}
> - D2: {摘要}
> - ...
>
> - **确认继续** — 按评审结论进入文档生成
> - **调整评审** — 修改已知问题或不采纳项的判定
> - **重新设计** — 问题过多，回到 CP4 提供新设计

等待用户回复。选择「调整评审」则根据用户反馈修改 REVIEW.md 后重新确认；选择「重新设计」则回到 CP4（不重新生成 Stitch prompts，用户可直接提供新设计文件）。

### CP5: 文档与初始化确认

**展示内容**（控制在 30 行内）：

即将创建以下内容：

**所有平台通用**（创建）：

| 文件/目录 | 说明 |
|-----------|------|
| `docs/01-discovery/project-brief.md` | 项目概要（含调研、定位、功能规划） |
| `docs/` 目录结构 | 10 个标准子目录 |
| `CLAUDE.md` | AI 助手项目规则（需先运行 /init） |
| `docs/00-AI-CONTEXT.md` | AI 上下文入口文档 |
| `docs/02-architecture/README.md` | 架构文档骨架 |
| `docs/05-features/README.md` | 功能文档模板 |
| `.github/ISSUE_TEMPLATE/` | GitHub Issue 模板和自定义 labels（如选择初始化） |

**仅 `platform==apple`（iOS/macOS）创建**——非苹果项目跳过下列项：

| 文件/目录 | 说明 |
|-----------|------|
| `CLAUDE.md` 内 `## Swift 6 并发` 段、Swift Design System token 表、平台 API 规则行 | 苹果专属约束 |
| `[项目名]/DesignSystem/DesignSystem.swift` | Design System 代码 |
| `docs/10-app-store-connect/` | ASC 文档模板（4 个文件） |
| Step 9.10 CI/CD 触发提示 | Xcode Cloud + GitHub Actions auto-version |
| CLAUDE.md `## Build Environment` 段 | xcodebuild 元数据表（step 9.2.2） |

**[Expectation Recap]**

告诉用户：「我准备帮你建项目骨架：写一份 project-brief、建 docs 目录、生成 CLAUDE.md{，`platform==apple` 时：初始化 Design System {如果有 Stitch 设计}、设置 ASC 文档模板、`platform==apple` 时的 CI/CD 初始化项}。这些一次性创建好之后，开发阶段就直接 /run-phase 推进。」
再问：「这套初始化范围你认吗? 不要的项告诉我跳过。」

**询问用户**（使用 AskUserQuestion）：

> 以上是将要创建的文档和项目结构。
>
> - **确认执行** — 创建全部文件
> - **调整内容** — 修改文件列表或内容后执行
> - **仅创建 project-brief** — 只创建项目概要文档，跳过项目初始化

等待用户回复。选择「仅创建 project-brief」则跳过步骤 9（初始化项目结构），直接进入步骤 10（下一步）。

### 8. 输出文档

将分析结果写入项目文档：

**文件路径**：`docs/01-discovery/project-brief.md`

Read `references/doc-templates.md` 的「project-brief.md 模板」段，按模板结构创建，根据步骤 1-6 的分析结果填充内容。

### 9. 初始化项目结构（按目标平台门控）

子步分为两类：
- **通用子步（所有平台执行）**：9.1 docs 结构 / 9.2 CLAUDE.md / 9.3 AI-CONTEXT / 9.4 architecture README / 9.5 features README / 9.7 不预建 / 9.9 Notion / 9.11 GitHub Issue
- **苹果专属子步（仅 `platform==apple`，非苹果项目跳过）**：9.2.1 平台 API 规则表 / 9.2.2 Build Env / 9.6 DesignSystem / 9.8 ASC / 9.10 CI-CD

模板内容在 references/ 目录中，按需加载。

#### 9.1 创建 docs 目录结构

Read `references/project-init-templates.md` 的「docs 目录结构」段，按模板创建 10 个标准子目录。

#### 9.2 创建 CLAUDE.md

**步骤 A**：提示用户运行 `/init` 生成基础 CLAUDE.md，等待完成。

**步骤 B**：Read `references/project-init-templates.md` 的「CLAUDE.md 追加模板」段，在 /init 生成的 CLAUDE.md 末尾追加项目特定内容（不替换 /init 生成的部分）。根据项目实际信息填充模板中的占位符。

**平台门控**（标记本身是 prose 指令，**不写入**生成的 CLAUDE.md）：
- `platform==apple`：写完整追加模板——含 `## Swift 6 并发（本项目）` 段、`编码规范` 下的 Swift Design System token 表（间距/布局/圆角/颜色/阴影）、`项目特定约束` 的 `必须：[由 9.2.1 生成的平台 API 规则]` 占位行。iOS 路径 = 现状（字节级不变）。
- `platform==other`：仅写通用骨架段（文档真相源 / 搜索约定 / 计划执行规则 / 完成功能后留档 / `## 编码规范` 的通用部分[通用规范指针 + UI 约束] / 遇到困惑 + 通用约束行如色觉无障碍），不写苹果专属段（`## Swift 6 并发` / Design System token 表 / 9.2.1 平台 API 占位）。

#### 9.2.1 平台 API 规则生成

**仅 `platform==apple`（iOS/macOS）；非苹果项目跳过。**

Read `references/project-init-templates.md` 的「平台 API 规则表」段。根据步骤 6 识别的功能列表查表匹配，将匹配到的「项目规则」写入 CLAUDE.md 的「项目特定约束」`必须：` 部分。

#### 9.2.2 Build Environment 信息采集

**仅 `platform==apple`（iOS/macOS）；非苹果项目跳过。**

**前置条件**：项目根目录存在 `.xcodeproj` 或 `.xcworkspace` 文件。如果都不存在（新建项目尚未创建 Xcode 工程），跳过本步。

**检测方式**：

```bash
# 优先使用 workspace（CocoaPods/SPM workspace）
workspace=$(find . -maxdepth 2 -name "*.xcworkspace" -not -path "*/DerivedData/*" | head -1)
project=$(find . -maxdepth 2 -name "*.xcodeproj" -not -path "*/DerivedData/*" | head -1)
```

如果找到 workspace 或 project：

1. 获取 scheme 列表：`xcodebuild -list -quiet 2>/dev/null`（如需 build 验证，优先 Apple MCP `BuildProject`；本步仅查元数据，无 MCP 等价，保持 CLI）
2. 选择主 scheme（排除含 `Tests`/`UI` 后缀的 scheme；仅一个 scheme 时直接使用；多个且无法判断时用 AskUserQuestion 让用户选择）
3. 采集 build settings：`xcodebuild -showBuildSettings -scheme "{scheme}" -quiet 2>/dev/null`
4. 从输出中提取以下字段：
   - `IPHONEOS_DEPLOYMENT_TARGET` 或 `MACOSX_DEPLOYMENT_TARGET`
   - `PRODUCT_BUNDLE_IDENTIFIER`
   - `DEVELOPMENT_TEAM`
   - `SWIFT_VERSION`
   - `TARGETED_DEVICE_FAMILY`（1=iPhone, 2=iPad, 1,2=Universal）
5. 在 CLAUDE.md 末尾追加：

```markdown
## Build Environment

| Setting | Value |
|---------|-------|
| Deployment Target | iOS {version} / macOS {version} |
| Bundle ID | {identifier} |
| Development Team | {team_id} |
| Swift Version | {version} |
| Device Family | iPhone / iPad / Universal |
| Scheme | {scheme_name} |
```

**错误处理**：
- `xcodebuild` 命令失败（返回非零）：跳过本步，不写入 Build Environment 段。不中断 kickoff 流程。
- 某个字段为空：该行写 `(not set)`。

#### 9.3 创建 docs/00-AI-CONTEXT.md

Read `references/doc-templates.md` 的「docs/00-AI-CONTEXT.md 模板」段，按模板创建，根据步骤 1-6 的分析结果填充内容。

**平台门控**（标记本身是 prose 指令，**不写入**生成的 AI-CONTEXT.md）：
- `platform==apple`：写入完整模板——含 `本地化` 段（`String(localized:)` / `.xcstrings`），技术栈/关键路径按 step 6 选型 + iOS 项目实际入口文件填充。
- `platform==other`：仅写通用骨架——跳过 `本地化` 整段；技术栈/关键路径按 step 6 + 项目实际入口填充，**不留下 iOS / `.swift` 示例**。

#### 9.4 创建 docs/02-architecture/README.md

简要描述：分层、数据流、模块依赖。后续可拆分为多个文件。

#### 9.5 创建 docs/05-features/README.md

Read `references/doc-templates.md` 的「docs/05-features/README.md 模板」段，按模板创建。

#### 9.6 Design System 初始化

**仅 `platform==apple`（iOS/macOS）；非苹果项目跳过。**

Read `references/doc-templates.md` 的「Design System 初始化」段。Token 来源识别顺序与步骤 7.5 一致：

1. 如果步骤 7.5.0 已记录 `docs/02-architecture/design-source.md` 且 format 为 Stitch DESIGN.md：
   - Read `references/doc-templates.md` 的「DESIGN.md → Swift Token 映射」段
   - 按映射表把 DESIGN.md 各 section 翻译为 Swift token 值，生成 `[项目名]/DesignSystem/DesignSystem.swift`
   - 不复制 DESIGN.md 内容到 Swift 注释；DESIGN.md 是 source of truth，Swift 是消费侧
   - 记录映射结果到 `docs/02-architecture/design-source.md` 的「Last sync」字段
2. 否则（DTCG JSON / HTML+CSS / 图片 / 跳过设计）：按映射段中对应的回退路径处理，未声明的维度走默认模板值

询问用户是否生成完整版 Design System（含 Component styles、 Animation tokens 等扩展）。如果用户确认，直接调用 `Skill("apple-dev:generate-design-system")` 执行，不中断流程。

完成后建议用户在迭代过程中通过 `Skill("apple-dev:sync-design-md")` 保持 DESIGN.md ↔ DesignSystem.swift 同步。

#### 9.7 不要预建的目录

以下目录按需创建，不预建空目录：`06-prompts/`、`08-guidelines/`

#### 9.8 App Store Connect 文档初始化

**仅 `platform==apple`（iOS/macOS）；非苹果项目跳过。**

Read `references/doc-templates.md` 的「App Store Connect 文档初始化」段，在 `docs/10-app-store-connect/` 下创建 4 个模板文件（privacy-policy、terms-of-use、support-page、market）。

#### 9.9 Notion 同步配置

Read `references/doc-templates.md` 的「Notion 同步配置」段。如果用户计划使用 Notion，按指引创建配置文件。

#### 9.10 CI/CD 配置初始化

**仅 `platform==apple`（iOS/macOS）；非苹果项目跳过。**

询问用户是否配置 CI/CD（Xcode Cloud + GitHub Actions 自动版本管理）。如果选 Yes，提示用户运行 `/setup-ci-cd`。

`/setup-ci-cd` 会：
- 统一所有 target 的版本号
- 启用 Apple Generic versioning
- 创建 GitHub Actions auto-version workflow（conventional commit → semver bump）
- 创建 Xcode Cloud ci_post_clone.sh（自动设置 build number）
- 输出 Xcode Cloud workflow 配置指引

#### 9.11 GitHub Issue 基础设施初始化

询问用户是否初始化 GitHub Issue 跟踪。如果选 No，跳过。

如果选 Yes：

1. Read `references/project-init-templates.md` 的「GitHub Issue Templates」段
2. 提取 owner/repo：`gh repo view --json owner,name -q '.owner.login + "/" + .name'`
3. 创建 `.github/ISSUE_TEMPLATE/bug.md` 和 `feature.md`（按模板内容）
4. 创建自定义 labels：`deferred`、`blocked`
5. 如果 dev-guide 已存在（`docs/06-plans/*-dev-guide.md`），为每个 phase 创建 label（`phase-N`）和 milestone
6. 如果 dev-guide 不存在，跳过 phase labels 和 milestones，提示用户：
   > Phase labels 和 milestones 需要 dev-guide。完成 `/write-dev-guide` 后，手动运行：
   > ```
   > gh label create "phase-1" --color "0E8A16" --description "Phase 1"
   > gh api repos/{owner}/{repo}/milestones -f title="Phase 1: {name}" -f description="{scope}"
   > ```
   > （具体命令见 `references/project-init-templates.md`「Milestones」段）

### 10. 下一步

项目初始化完成。根据项目复杂度选择：

- **需要深度设计探索** → `/brainstorm` → `/write-dev-guide` → `/run-phase`
- **设计已明确，直接开始** → `/write-dev-guide` → `/run-phase`
- **简单项目** → 直接做（无需 dev-guide / phase 编排），如需结构化任务拆分可用 `/write-plan`

## 原则

1. **不编造**：所有竞品信息来自真实搜索，附链接。**文献引用另有一道硬门**：作者、年份、期刊、DOI 一律不得凭记忆补，每条结论都要有 WebFetch 抓到的摘要页原文兜底；抓不到就标 ⚠️ 当假说，不写进结论。引用格式看着可核验但实际不可核验，是本流程最强的编造载体
2. **客观分析**：不美化用户想法，指出真实风险
3. **可操作**：MVP 规划要具体，不泛泛而谈
4. **敢说不**：如果方向不可行，直接说
