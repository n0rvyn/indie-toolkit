# iOS App Version 页面

## 1. Previews and Screenshots（预览和截图）⚠️ 必须准备

**必须准备的尺寸**：

| 设备 | 尺寸（px） | 说明 |
|------|-----------|------|
| **iPhone 6.7"** | 1290 × 2796 | iPhone 15 Pro Max, 16 Pro Max |
| **iPhone 6.5"** | 1242 × 2688 或 1284 × 2778 | iPhone 14 Plus, 15 Plus |
| **iPhone 5.5"** | 1242 × 2208 | iPhone 8 Plus（可选，向下兼容） |
| **iPad 12.9"** | 2048 × 2732 | 如支持 iPad |

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
