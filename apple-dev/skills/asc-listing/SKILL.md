---
name: asc-listing
description: "Everything on the App Store Connect backend: what to put in each box, and what the backend actually holds right now. Use when the user says 'ASC listing', 'asc 上架材料', 'ASC 填写', 'app store listing', 'privacy labels', or asks to read the live state — 'ASC 现在填的是什么', '关键词字段实际是什么', '我改的 ASC 字段存进去了吗', '提交出去了吗', 'read back ASC', 'check ASC state', 'is it actually submitted' — or after any ASC edit that must be confirmed. Covers item-by-item submission material guidance, authenticated read-back of live keywords / name / subtitle / description / promo / What's New / review notes / screenshot checksums, whether a version is really queued with Apple, and version-to-version diffing for post-rejection forensics. Keywords: ASC, App Store Connect, submission, privacy labels, screenshots, review, read-back, submission state. Not for 代码合规检查 — use /asc-submit-preview. Not for 关键词研究 / 商店搜索排名 / 商标能否进名称 — use /aso-research (this skill reads and fills the ASC boxes; that one decides what the text should be, from pulled ranking data)."
---

# App Store Connect 上架审查

逐项指导 App Store Connect 中 iOS/macOS App 上架需要填写的内容，或执行提交前审计。

参考资料在 `asc-listing/references/` 目录中（相对于 skills 目录），按需加载。

## Process

### Step 1: 确定审查模式

从用户消息判断：

**模式 A — 全量填写指导**：用户首次上架或说"帮我填 ASC"。按顺序引导所有字段。

**模式 B — 隐私标签**：用户专门问隐私标签。聚焦 App Privacy 部分。

**模式 C — 特定部分**：用户问某个具体字段或部分。加载对应 reference 段落回答。

**模式 D — 读回现状**：用户问「现在填的是什么」「我改的存进去了吗」「提交出去了吗」，或刚在 ASC 后台改完东西要确认。走「读回后端真实内容」一节，用脚本拉，不猜。

> 历史说明：早期版本含"代码合规审计"模式，已迁移到 `/asc-submit-preview`。本 skill 不再处理代码合规，专注 ASC 后台材料（隐私标签 / 截图 / 描述 / 价格 / 关键词）。

> **与 `/aso-research` 的分工**：本 skill 管「每个框该怎么填、别漏填」；名称 / 副标题 / 关键词该填**什么文字**，需要实拉商店数据才能定 —— 那是 `/aso-research`。用户问到关键词该写什么、为什么搜不到、第三方商标能不能用时，转过去。

### Step 2: 加载参考资料

根据模式加载对应 reference：

| 模式 | 加载文件 |
|------|---------|
| A | `references/asc-fields-guide.md` → `references/asc-version-and-review.md` → `references/asc-audit-checklist.md`（准备清单部分） |
| B | `references/asc-fields-guide.md`（第二部分：App Privacy） |
| C | 根据用户问题定位对应 reference 的具体段落 |
| D | 不加载 reference，直接跑「读回后端真实内容」一节的脚本 |

### Step 3: 执行审查

**模式 A**：按 reference 中的字段顺序，逐项向用户解释并确认填写内容。每完成一个大部分（App Information / Privacy / Version），确认再进入下一部分。

**模式 B**：读取项目代码（import 语句、网络请求、数据存储），帮用户判断每个数据类型是否需要声明。输出格式：

```
[隐私标签审查]
| 数据类型 | 是否收集 | 证据 | 建议 |
|---------|---------|------|------|
| Health | ✅ | import HealthKit in ... | 声明，关联用户，App Functionality |
| Location | ❌ | 无相关 import/API | 不声明 |
```

**模式 C**：直接回答用户问题，引用 reference 中的具体指引。

**模式 D**：按「读回后端真实内容」一节执行，四条纪律：

1. **先定 App**。标识符不确定就先跑 `apps`，绝不猜 app id。
2. **任何关于「某字段现在是什么」的断言，必须贴 `show` / `assert` 的输出**，不许来自记忆、也不许来自仓库里的文案文档——本地副本与后端会漂移。
3. **ASC 改完之后，先 `assert --present` 再 `state`**，顺序不能反：字段存进去了不等于提交出去了。
4. **被拒之后先 `diff` 再提假说。** 先分清哪些字段真的变了。
5. **报你看到的数字。** 关键词字段上限 100 字符，`show` 直接打实测长度，不要目测估。

### Step 3.5: 描述里的每条功能，回代码找落点（模式 A 必做）

**这一步没有别人管。** `asc-submit-preview` 查代码 vs 审核指南，本 skill 查表单填没填全，`aso-research` 定文案写什么 —— **「描述里写的功能，二进制里到底有没有」落在三者的缝里**，而它是 2.3.1（描述与实际不符）整类拒审的来源。

做法：把描述与推广文本里的**每一条功能句**拆出来，各找一个代码落点 —— 一个 View、一个 target、一个 entitlement、一个 framework import。找不到落点的，就是候选缺陷。

```
| 描述里的功能句 | 代码落点 | 判定 |
|---|---|---|
| 实时照度读数 | Sensing/AmbientLightProvider.swift | ✅ |
| 锁屏实时活动与灵动岛 | 无 Widget Extension target；节点仍是 #warning("FLOW-STUB") | ⛔ 删掉这句 |
```

⚠️ **最容易漏的两种落点缺失**：

1. **需要独立 target 的能力**（Live Activity / Widget / App Clip / Watch App）—— App target 里有几行相关代码不等于功能存在。查 `xcodebuild -list` 的 target 列表。
2. **半成品脚手架**：`#warning("FLOW-STUB")`、`TODO`、占位 View。它们编译得过、跑起来也不崩，只是渲染一个占位页 —— 纯代码审查和跑测试都抓不到，只有对着描述逐句核才会暴露。

功能确实要交付但还没写完时，这条不是「删掉文案」，是**变成打包前置条件**：写进阻塞项，功能进版本库之后才允许 Archive。

### Step 4: 输出报告

**模式 A/B**：输出已确认的字段值汇总，标注待用户补充的项。

⛔ **报告里写 `✅ 已填 / 已通过` 的每一格，必须有你自己刚取到的观测撑着。** 用户口述「都填了」、上一轮的记忆、项目文档里的记录，都不算 —— 一份写着 `✅` 而实际没查过的提交清单比不写更糟，它会让人跳过检查。查不到的（ASC API 不暴露的字段）标 `⚠️ 需后台确认`，不要留空白也不要打勾。

## 读回后端真实内容（模式 D，其它模式也先跑一遍）

**开工前先拉一遍现状。** 很多字段创建 App 时就设好了，照着 reference 从头问一遍，会问出一堆 API 一次就能答的问题。

两件公开接口和 ASC 网页都办不到的事，只有鉴权 GET 能办：

1. **「填了但没保存」** —— ASC 表单在字段提交成功与否两种情况下长得一模一样。
2. **「改了但没提交」** —— 被拒之后改字段并保存**不会**让 App 重新排队。无报错、无提示。

另外，**关键词字段公开接口读不到**，所以 `/aso-research` 只能从排名反推；这里能逐字读出来。

### 脚本

```bash
SC=${CLAUDE_SKILL_DIR}/scripts/asc_readback.py     # 每条都是 GET，改不了任何东西
python3 $SC apps                                    # 账号下所有 App
python3 $SC show <app> [--limit N] [--screenshots] [--full]
python3 $SC state <app>                             # 到底在 Apple 那儿排队了没有
python3 $SC diff <app> 2.4 2.5                      # 变量 vs 常量，被拒后先跑这个
python3 $SC assert <app> --locale zh-Hans --field keywords --present 记账
```

`<app>` 接受 bundle id、数字 app id、或不区分大小写的名称子串。

**凭据**：需要一个 App Store Connect API 密钥（`AuthKey_XXXXXXXX.p8`，App Manager 或 Developer 权限）与 `python3 -m pip install cryptography`。查找顺序：① `ASC_KEY_PATH` + `ASC_KEY_ID` + `ASC_ISSUER_ID` ② `ASC_KEY_PATH` 加同目录 `key.info`（含 `Key ID:` 与 `Issuer ID:` 两行，Apple 界面里写的是 `Issue ID`，两种拼法都认）③ 扫 `~/private_keys`、`~/.appstoreconnect/private_keys`、以及 `ASC_KEY_DIRS`（冒号分隔）下的第一个 `AuthKey_*.p8` 加同目录 `key.info`。

一次性配好的做法：把 `.p8` 与 `key.info` **软链**进 `~/private_keys/`，此后任何项目都不用再指路，也不用环境变量。⛔ 密钥、Key ID、Issuer ID 一个字都不许写进会进仓库的文件。

### `state` —— 判据是提交单的 state，不是条目的 state

| 字段 | 未提交 | 重新提交后 | 能不能当判据 |
|---|---|---|---|
| `reviewSubmissions[].state` | `UNRESOLVED_ISSUES` | `WAITING_FOR_REVIEW` | ✅ **就看这个** |
| `reviewSubmissions[].submittedDate` | 旧时间戳 | 会更新 | ✅ 佐证 |
| `reviewSubmissions/{id}/items[].state` | `READY_FOR_REVIEW` | **仍是 `READY_FOR_REVIEW`** | ❌ 永远不动 |

条目的 `state` 是**结论**字段（`READY_FOR_REVIEW` → `APPROVED` / `REJECTED`），从不经过 `WAITING_FOR_REVIEW`，拿它回答「我提交了吗」两种情况返回同一个值。2026-08-28 在一次真实重新提交上实测。⚠️ 这与 Apple 帮助页的措辞冲突——那页描述的是**网页端**的状态标签，不是 API 的条目字段。以实测为准。

退出码：**只有真的 `WAITING_FOR_REVIEW` / `IN_REVIEW` 才是 0**，其余全是 1（被拒未重提、已暂存未提交、全部已完成、从未提交过）。所以 `… && python3 $SC state <app>` 卡的是「真的在排队」，不是「命令跑成功了」。已上架且无待审版本时它也报 ⛔ 退出 1，这是对的。

### `assert` —— 改完就跑，确认存盘

```bash
python3 $SC assert <app> --locale zh-Hans --field keywords --present 记账 \
  && python3 $SC assert <app> --locale zh-Hans --field keywords --absent openai \
  && python3 $SC state <app>
```

⚠️ **确认「存进去了」只能用 `--present` / `--equals`，不能用 `--absent`。** 空字段不含任何违禁词，`--absent` 在一个被静默丢掉的字段上会空过——正是上面失败模式 #1。`assert` 每行都打字符数，0 字符会大声警告，但真正证明写入落地的是 `--present`。`--absent` 留给合规检查。

版本字段只在**选定的那一个版本**内解析（默认最新，或 `--version`），不跨版本回落；输出会打印数据来源（`v1.1/zh-Hans/keywords`）。

### `diff` —— 被拒之后先分清变量和常量

两版之间**相同**的字段是常量，不是这次的变量：审核结论变了，原因在**不同**的那些字段里，不管相同的那些看起来多可疑。截图的 `sourceFileChecksum` 也在比对范围内，所以「这张图和上次过审的是不是同一张」是可答的。输出对齐在**第一个不同的字符**上，不是字符串开头——长描述通常只在结尾不同。

### 脚本没覆盖、要手打端点的

| 想知道 | 端点 |
|---|---|
| 类目 | `/v1/appInfos/{id}/primaryCategory`（`secondaryCategory` 同理） |
| 年龄分级各项申报 | `/v1/appInfos/{id}/ageRatingDeclaration` |
| 版权 / 发布方式 | `/v1/appStoreVersions/{id}` |
| 构建版本 | `/v1/apps/{id}/builds` |
| 定价 / 内购 / 订阅 | `/v1/appPriceSchedules/{appId}/manualPrices?include=appPricePoint,territory`、`/v1/apps/{id}/inAppPurchasesV2`、`/subscriptionGroups` |

（名称 / 副标题 / 隐私政策 URL / 描述 / 关键词 / 推广文本 / 支持 URL / 营销 URL / 更新说明 / 审核备注 / 截图校验和，`show` 全都覆盖，别再手打。截图**在 localization 层，不在 version 层**，见 `references/asc-version-and-review.md`。）

### 读回的边界

- **截图画面是图，脚本读不了。** 只看得见文件名与校验和。品牌名烧进截图美术稿里的，只能人眼看——那是一条真实的拒审路径。
- 商店元数据按 **locale** 组织，不按国家/地区。没有「只改某国」的关键词字段，所以针对单一国家的合规要求，要么改全局文案，要么下架该商店。
- 单次读可能撞上传播延迟。判断状态变化时，隔几分钟读两次再下结论。
- 版本顺序 Apple 不保证：`appStoreVersions` 与 `reviewSubmissions` 都没有 `sort` 参数、也没承诺默认顺序（2026-08-28 对着 Apple 文档核过）。脚本按 `createdDate` / `submittedDate` 在本地排序并打印时间戳——看时间戳，别信位置。`diff` 与 `assert --version` 显式锁版本，完全不依赖顺序。
- 只读。写元数据是**故意不做**的：一次错误的 PATCH 打到线上 listing，撤回不便宜。把确切字符串交给用户去粘，然后 `assert`。

**读不到的（别浪费探针去找）**：

- **App Privacy 隐私标签** —— ASC API 不暴露，只能在后台确认。本 skill 的模式 B 产出的是「该怎么勾」的判断，不是「勾没勾」的核实。
- **许可协议（标准 / 自定义）** 与 **数字服务法案 Trader 身份** —— 同样不暴露。
- `/v1/apps/{id}/appEncryptionDeclarations` 返回 404（该关系不存在）。加密声明看 `Info.plist` 的 `ITSAppUsesNonExemptEncryption`，不看 API。

## Completion Criteria

- 用户确认的模式已完成
- 所有检查项有明确结果（通过/不通过/待确认）
- 不通过的项有具体修复建议
- **描述里每条功能都找到了代码落点**（Step 3.5），找不到的已列为阻塞项
- 报告里每个 `✅` 都有本轮实拉/实查的证据，没有转述
- 模式 D：每条现状断言都贴了脚本输出；若本轮在 ASC 改过东西，`assert` 与 `state` 都跑过且报了退出码

## 串联提示

✅ ASC 上架审查完成。

**ASO 优化**（与 ASC 合规审查互补，关注 metadata discoverability）：
- App Store 关键词 / 标题 / 副标题 / description 优化与本地化策略 → grep `apple-dev/references/aso-guide.md`
