---
name: asc-listing
description: "Use when preparing ASC store listing materials, or the user says 'ASC listing', 'asc 上架材料', 'ASC 填写', 'app store listing', 'privacy labels'. Performs item-by-item App Store Connect submission material check and guidance. Keywords: ASC, App Store Connect, submission, privacy labels, screenshots, review. Not for 代码合规检查 — use /asc-submit-preview. Not for 关键词研究 / 商店搜索排名 / 商标能否进名称 — use /aso-research (this skill guides what to type in each ASC box; that one decides what the text should be, from pulled data)."
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

> 历史说明：早期版本含"代码合规审计"模式，已迁移到 `/asc-submit-preview`。本 skill 不再处理代码合规，专注 ASC 后台材料（隐私标签 / 截图 / 描述 / 价格 / 关键词）。

> **与 `/aso-research` 的分工**：本 skill 管「每个框该怎么填、别漏填」；名称 / 副标题 / 关键词该填**什么文字**，需要实拉商店数据才能定 —— 那是 `/aso-research`。用户问到关键词该写什么、为什么搜不到、第三方商标能不能用时，转过去。

### Step 2: 加载参考资料

根据模式加载对应 reference：

| 模式 | 加载文件 |
|------|---------|
| A | `references/asc-fields-guide.md` → `references/asc-version-and-review.md` → `references/asc-audit-checklist.md`（准备清单部分） |
| B | `references/asc-fields-guide.md`（第二部分：App Privacy） |
| C | 根据用户问题定位对应 reference 的具体段落 |

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

## ASC API 能读什么、不能读什么

有 ASC API 凭据时（`ASC_KEY_ID` + `ASC_ISSUER_ID` + `.p8`，ES256 JWT），**先拉一遍现状再问用户** —— 很多字段创建 App 时就已经设好了，照着 reference 从头问一遍会问出一堆 API 一次就能答的问题。

| 想知道 | 端点 |
|---|---|
| 名称 / 副标题 / 隐私政策 URL | `/v1/appInfos/{id}/appInfoLocalizations` |
| 描述 / 关键词 / 推广文本 / 支持 URL / 营销 URL / 更新说明 | `/v1/appStoreVersions/{id}/appStoreVersionLocalizations` |
| 类目 | `/v1/appInfos/{id}/primaryCategory`（`secondaryCategory` 同理） |
| 年龄分级各项申报 | `/v1/appInfos/{id}/ageRatingDeclaration` |
| 版权 / 发布方式 / 版本状态 | `/v1/appStoreVersions/{id}` |
| 审核联系人与备注 | `/v1/appStoreVersions/{id}/appStoreReviewDetail`（未创建时返回 `data: null`） |
| 构建版本 | `/v1/apps/{id}/builds` |
| 定价 / 内购 / 订阅 | `/v1/appPriceSchedules/{appId}/manualPrices?include=appPricePoint,territory`、`/v1/apps/{id}/inAppPurchasesV2`、`/subscriptionGroups` |
| 截图 | 见 `references/asc-version-and-review.md` —— **在 localization 层，不在 version 层** |

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

## 串联提示

✅ ASC 上架审查完成。

**ASO 优化**（与 ASC 合规审查互补，关注 metadata discoverability）：
- App Store 关键词 / 标题 / 副标题 / description 优化与本地化策略 → grep `apple-dev/references/aso-guide.md`
