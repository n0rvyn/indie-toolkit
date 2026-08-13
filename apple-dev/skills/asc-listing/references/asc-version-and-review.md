# iOS App Version 页面

## 1. Previews and Screenshots（预览和截图）⚠️ 必须准备

### 尺寸对照表（ASC 硬校验，错一像素即拒收）

| 槽位 | 可接受像素 | 机内屏幕 pt | 倍率 |
|---|---|---|---|
| iPhone 6.9" | 1290×2796 / 2796×1290 | 430×932 | @3x |
| iPhone 6.5" | 1284×2778 / 1242×2688 | 428×926 / 414×896 | @3x |
| iPhone 5.5" | 1242×2208 | 414×736 | @3x |
| iPad 12.9" / 13" | 2064×2752 / 2048×2732 | 1032×1376 / 1024×1366 | @2x |
| Mac | 2880×1800 / 2560×1600 | — | @2x |

规则：**机内屏幕的 pt 尺寸必须与画布像素同源**（画布像素 ÷ 倍率）。缩放系数 = 机身内屏宽度(px) ÷ 屏幕 pt 宽度。

一个槽位的图会向下适配更小机型，所以通常只做最大的那档 + iPad（如果 App 支持 iPad）。

#### ⚠️ 「最大的那档」不等于 6.9" —— 两个槽位的实测值（直接用，别再问）

**2026-08-13 在 ASC 上逐字确认（ArtLens 上架流程），两个槽位都记在这里：**

```
iPhone —— Screenshots dimensions should be:
1242 × 2688px, 2688 × 1242px, 1284 × 2778px or 2778 × 1284px

iPad ———— Screenshots dimensions should be:
2064 × 2752px, 2752 × 2064px, 2048 × 2732px or 2732 × 2048px
```

iPhone 是 **6.5" 档**——里面根本没有 1290×2796。按 6.9" 画完再发现要 6.5"，全套画布、机身、机内屏幕 pt 都要改一遍。
iPad 两组都收：2064×2752 是 13"（1032×1376 pt），2048×2732 是 12.9"（1024×1366 pt），任选其一。

**唯一真源仍然是 ASC 页面那一行**——但它已经被抄在上面了，所以默认按上面开工。

#### 想知道某个 App 现在挂着哪些槽位

ASC API 的截图**挂在 localization 层，不在 version 层**：

```
/v1/appStoreVersions/{verId}/appStoreVersionLocalizations
  → /v1/appStoreVersionLocalizations/{locId}/appScreenshotSets   ← 真正的挂载点
    → /v1/appScreenshotSets/{setId}/appScreenshots
```

⛔ `/v1/appStoreVersions/{verId}/appScreenshotSets` 返回 **200 + 空数组** —— 关系存在但不是挂载点。照它读会得出「一张截图都没有」的错误结论，而这个空数组同时兼容「真没传」和「查错了对象」，判别力为零。**先拿一个已上架 App 跑同一条查询确认能返回非零，再信它给你的零。**

`screenshotDisplayType` 的取值就是槽位名：`APP_IPHONE_65`、`APP_IPHONE_67`、`APP_IPAD_PRO_3GEN_129` 等。

**截图要求**：
- 每个尺寸最少 1 张，最多 10 张
- 前 3 张最重要（安装页面预览）
- 必须是真实 App 界面，不能是 mockup
- 建议展示核心功能流程

**App Preview 视频（可选）**：
- 15-30 秒
- 与截图相同尺寸
- 每个尺寸最多 3 个

## 2. Promotional Text（宣传文本）

| 限制 | 170 字符 |
|------|----------|
| 特点 | 随时可改，不需要新版本审核 |
| 用途 | 突出核心卖点，可用于限时促销 |

## 3. Description（详细描述）

| 限制 | 4000 字符 |
|------|----------|
| 特点 | 需要提交新版本才能修改 |

**结构建议**：
```
[一句话介绍核心价值]

【主要功能】
• 功能1
• 功能2
• 功能3

【特色亮点】
• 亮点1
• 亮点2

【适合人群】
• 人群1
• 人群2

【隐私与安全】（建议添加）
简述数据处理方式
```

## 4. Keywords（关键词）

| 限制 | 100 字符，逗号分隔 |
|------|-------------------|
| 技巧 | 不要重复 App 名称、不要用竞品名、用单词而非短语 |

## 5. URLs

| 字段 | 必填 | 说明 |
|------|------|------|
| **Support URL** | ✅ 必填 | 用户支持页面。可以是网页、社交媒体、或 GitHub Issues |
| **Marketing URL** | 可选 | 产品官网或落地页 |

## 6. Version & Copyright

| 字段 | 格式 | 示例 |
|------|------|------|
| **Version** | 与 Xcode 一致 | `1.0`, `1.0.1` |
| **Copyright** | © 年份 名称 | `© 2024 Your Name` |

## 7. Build

上传方式：
1. **Xcode**：Product → Archive → Distribute App → App Store Connect
2. **命令行**：`xcodebuild archive` + Transporter
3. **CI/CD**：Fastlane、GitHub Actions 等

## 8. App Review Information（审核信息）⚠️ 重要

### Sign-In Information（登录信息）
| 情况 | 操作 |
|------|------|
| App 需要登录才能使用主要功能 | 提供测试账号和密码 |
| 无需登录即可使用 | 关闭 `Sign-in required` 开关 |
| 使用 Apple ID 登录 | 仍需提供测试账号或说明如何创建 |

### Contact Information（联系信息）
| 字段 | 说明 |
|------|------|
| First Name / Last Name | 审核联系人姓名 |
| Phone Number | 电话（含国家代码，如 +86 138...） |
| Email | 审核相关邮件会发到这里 |

**注意**：审核员可能会在工作时间（美国时间）打电话

### Notes（审核备注）
向审核员说明：
- App 主要功能
- 如何测试特定功能
- 需要特殊硬件或条件的功能说明
- 健康类 App 的医疗声明

### Attachment（附件）
可上传截图或视频，用于：
- 演示特殊功能
- 说明需要特定条件才能触发的功能
- 提供测试用的二维码等

## 9. App Store Version Release（发布方式）

| 选项 | 说明 | 适用场景 |
|------|------|----------|
| **Manually release** | 审核通过后手动发布 | 首次上架、重大版本 |
| **Automatically release** | 审核通过后自动发布 | Bug 修复、小更新 |
| **Scheduled release** | 指定时间发布 | 配合市场活动 |
