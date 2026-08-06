# 第三方商标能用到哪个字段

App 对接第三方服务（Garmin、Strava、Notion、Claude、微信…）时，「能不能提这个品牌」问错了会把品牌词放进最容易被驳回的字段。

**答案是分字段的，不是一个是非题。**

## 官方条款原文

来源：<https://developer.apple.com/app-store/review/guidelines/>（2026-08-06 拉取）

**4.1(c) Copycats**
> You cannot use another developer's icon, brand, or product name in your app's **icon or name**, without approval from the developer.

作用范围只有 icon 和 name。副标题、关键词、描述都不在这句话里。

**4.1(a)**
> Don't simply copy the latest popular app on the App Store, or make some **minor changes to another app's name** or UI and pass it off as your own.

**2.3.7 Metadata**
> Choose a unique app name, assign keywords that accurately describe your app, and **don't try to pack any of your metadata with trademarked terms, popular app names, pricing information, or other irrelevant phrases just to game the system.** … App subtitles … should not include inappropriate content, **reference other apps**, or make unverifiable product claims. **Apple may modify inappropriate keywords at any time** or take other appropriate steps to prevent abuse.

禁的是「堆砌 + 为刷排名 + 与 App 无关」这一组条件同时成立。对关键词，Apple 写明的处置是**改掉**，不是驳回。

**5.2.1**
> Don't use protected third-party material such as trademarks... without permission, and don't include misleading, false, or copycat representations, names, or metadata.

## 逐字段结论

| 字段 | 能不能放第三方品牌 | 依据 |
|------|:--:|------|
| App 名称 | **不能** | 4.1(c) 明文 |
| 图标 | **不能** | 4.1(c) 明文 |
| 副标题 | **能**，用指代式 | 2.3.7 只禁 packing to game the system |
| 关键词 | **能** | 同上；Apple 的处置是改掉不是驳回 |
| 描述 | **能** | 无禁令，受 5.2.1 的不得误导约束 |
| 推广文本 | **能** | 同描述，且不索引、随时可改 |

## 写法

副标题用**指代式**，不要以裸品牌开头：

- ✅ `Route models for Claude Code` · `Sync for Garmin CN & Global` · `适用于佳明 Garmin Connect 的活动互传`
- ⚠️ `Garmin Connect 双区同步` —— 品牌打头，2.3.7 那句「should not reference other apps」咬得更紧

指代式明确表达「兼容 / 适用于」而非「出自」，这正是 4.1(c) 真正防的冒充。

关键词里可以放本 App **实际对接**的服务品牌。**不能**放竞品 App 名 —— 那正是 2.3.7 说的「popular app names」和「irrelevant phrases」，且本 App 不对接它，写了同时构成虚假描述。

名称与图标里一个商标字都不放。名称是唯一改动要走完整审核周期的字段，没有理由拿它赌。

## 验证方法

不要凭本文档下结论，按顺序取证：

1. **问用户有没有被拒历史。** 同账号的实际驳回记录权重最高，一条就能推翻所有在架推断。
2. **查同账号其它 App。** 用 `viewSoftware` 拉该开发者已过审的 App 的副标题与描述，看第三方品牌实际用到了哪一层。这是最贴切的先例。
3. **反推关键词字段。** iOS 端参与搜索索引的只有名称、副标题、关键词、开发者名、内购名（描述不索引）。若某 App 为某品牌词排名而名称与副标题都不含该词，则该词必在关键词字段里且已过审。
4. **拉在架第三方案例。** 品牌词搜索前 50 名里，开发者不是品牌方却在名称里用了该品牌的 App。

## 一个必须说清的矛盾

第 4 步经常能捞到一批名称含第三方品牌的在架 App（`Camera for Garmin`、`Dride for Garmin`、`Flying the Garmin GTN650/750`…），与 4.1(c) 的字面规定冲突。

三种可能：拿到了权利人书面授权、老提交沿用、审核员判断不一致。**Apple 不公开授权记录，无法区分是哪一种。**

因此：**「别人架上有」不构成可依赖的依据**，尤其当用户已经因为同类名称被拒过。第 1 步和第 2 步的证据等级高于第 4 步。

## 实证案例（2026-08，同一开发者账号）

| 字段 | 案例 | 结果 |
|------|------|------|
| 名称 | `Garmin Link` | **被反复拒绝** |
| 副标题 | Model Proxy（Mac App Store）`Route models for Claude Code` | 过审 |
| 关键词 | Activity Bridge 名称与副标题均无 Garmin 字样，却在 CN「佳明」排 99、US「garmin」排 44 | 过审（反推法） |
| 描述 | Model Proxy 描述含 Claude / Codex / Anthropic / DeepSeek / MiniMax / Kimi | 过审 |
