# App Store Connect 字段填写指南

## 第一部分：App Information 页面

### 1. Localizable Information（可本地化信息）

| 字段 | 类型 | 限制 | 填写说明 |
|------|------|------|----------|
| **Name** | 文本 | 最多 30 字符 | App 在 App Store 显示的名称。简洁有辨识度，避免通用词汇 |
| **Subtitle** | 文本 | 最多 30 字符 | 名称下方的副标题。突出核心价值或差异化卖点 |

### 2. General Information（通用信息）

| 字段 | 类型 | 说明 |
|------|------|------|
| **Bundle ID** | 只读 | 从 Xcode 读取，无需填写 |
| **SKU** | 只读 | 创建 App 时设置，内部标识，用户不可见 |
| **Apple ID** | 只读 | 系统自动生成 |

### 3. Content Rights（内容权利）

**选项**：
- `Yes, this app has the necessary rights to its third-party content` — 如果 App 包含第三方内容（图片、数据库、API 数据、字体等）
- `No, it doesn't contain, show, or access third-party content` — 完全自己创作的内容

**常见需要选 Yes 的情况**：使用第三方 API、图标库、字体、数据库、SDK

### 4. License Agreement（许可协议）

**选项**：
- `Apple's Standard License Agreement` — 大多数 App 选这个
- `Custom App License Agreement` — 需要自定义条款时（如企业 App）

### 5. Primary Language（主要语言）

App Store 列表的默认语言。用户所在区域无本地化版本时显示此语言。

### 6. Category（类别）

选择最符合 App 核心功能的类别。可选一个主类别和一个次类别。

**常用类别**：
- Health & Fitness（健康与健身）
- Productivity（效率）
- Utilities（工具）
- Lifestyle（生活）
- Finance（财务）

### 7. Age Ratings（年龄分级）⚠️ 重要

需要回答一系列问题，系统自动计算分级。如实回答，错误可能导致拒审。

#### Step 1: Features（功能特性）
| 问题 | 说明 |
|------|------|
| Parental Controls | App 是否包含家长控制功能 |
| Age Assurance | App 是否验证用户年龄 |
| Unrestricted Web Access | App 是否允许访问任意网页 |
| User-Generated Content | App 是否有用户创建/分享内容的功能（社区、评论等） |
| Messaging and Chat | App 是否有用户间的即时通讯功能 |
| Advertising | App 是否包含广告 |

#### Step 2: Mature Themes（成人主题）
| 问题 | 选项说明 |
|------|----------|
| Profanity or Crude Humor | 脏话或粗俗幽默 |
| Horror/Fear Themes | 恐怖或惊悚内容 |
| Alcohol, Tobacco, or Drug Use | 酒精、烟草或毒品相关内容 |

**选项**：NONE（无）/ INFREQUENT（偶尔）/ FREQUENT（频繁）

#### Step 3: Medical or Wellness（医疗或健康）
| 问题 | 说明 |
|------|------|
| Medical or Treatment Information | 是否提供医疗或治疗信息 |
| Health or Wellness Topics | 是否涉及健康或养生话题 |

**健康类 App 注意**：涉及健康话题选 YES，通常会被评为 12+ 或 13+

#### Step 4: Sexuality or Nudity（性或裸露）
通常全部选 NONE

#### Step 5: Violence（暴力）
通常全部选 NONE

#### Step 6: Chance-Based Activities（随机性活动）
| 问题 | 说明 |
|------|------|
| Simulated Gambling | 模拟赌博（不涉及真钱） |
| Contests | 竞赛活动 |
| Gambling | 真实赌博（涉及真钱） |
| Loot Boxes | 抽卡/开箱机制 |

### 8. App Encryption Documentation（加密声明）

**在 Info.plist 中设置**：
```xml
<key>ITSAppUsesNonExemptEncryption</key>
<false/>
```

**选择 NO（false）的条件**：
- 仅使用 HTTPS
- 仅使用 iOS 系统加密 API（如 CryptoKit、Security framework）
- 不包含自定义加密算法

**需要选 YES 并上传文档的情况**：
- 使用自定义加密算法
- 使用非标准加密库

### 9. Digital Services Act（数字服务法案）

欧盟要求。选择是否以商业身份（Trader）发布 App。

---

## 第二部分：App Privacy（隐私标签）⚠️ 必须填写

App Store Connect 中独立的隐私信息页面。用户在 App Store 看到的「App 隐私」标签由此生成。

### 填写流程

1. 选择 App 收集的所有数据类型
2. 对每个数据类型回答三个问题：是否用于追踪、是否关联用户身份、收集目的
3. 发布后立即生效；移除数据类型也会立即更新

### 数据类型完整清单

逐项检查 App 是否收集以下数据。**判断标准**：数据是否离开设备（发送到你的服务器或第三方），或在设备上被用于追踪/广告目的。

**不需要声明的情况**：
- 仅在设备本地处理、从未发送到服务器的数据
- 仅发送给 Apple 自有服务的数据（WeatherKit、MapKit、Sign in with Apple、Apple Pay、iCloud 等）— Apple 在自己的隐私政策下处理这些数据
- 满足「可选披露」条件的数据（见下方）

#### Contact Info（联系信息）
| 数据类型 | 说明 | 常见场景 |
|---------|------|---------|
| Name | 姓名 | 注册/登录、个人资料 |
| Email Address | 邮箱（含哈希） | 注册/登录、通讯 |
| Phone Number | 电话（含哈希） | 注册/验证 |
| Physical Address | 物理地址 | 配送、账单 |
| Other User Contact Info | 其他联系方式 | 社交账号等 |

#### Health & Fitness（健康与健身）
| 数据类型 | 说明 | 常见场景 |
|---------|------|---------|
| Health | 健康医疗数据 | HealthKit API、Clinical Records、运动障碍 API |
| Fitness | 健身运动数据 | Motion and Fitness API、运动追踪 |

#### Financial Info（财务信息）
| 数据类型 | 说明 | 常见场景 |
|---------|------|---------|
| Payment Info | 支付信息 | 若由 Apple 处理（StoreKit），无需声明 |
| Credit Info | 信用信息 | 信用评分等 |
| Other Financial Info | 其他财务 | 收入、资产等 |

#### Location（位置）
| 数据类型 | 说明 | 常见场景 |
|---------|------|---------|
| Precise Location | 精确位置（≥3 位小数） | GPS 定位 |
| Coarse Location | 粗略位置 | IP 定位、城市级别 |

#### Sensitive Info（敏感信息）
种族、性取向、怀孕、残疾、宗教信仰、工会、政治观点、基因、生物识别数据。

#### Contacts（通讯录）
用户手机/地址簿/社交图谱中的联系人列表。

#### User Content（用户内容）
| 数据类型 | 说明 | 常见场景 |
|---------|------|---------|
| Emails or Text Messages | 邮件/消息内容 | 邮件客户端、聊天 App |
| Photos or Videos | 照片/视频 | 上传到服务器的媒体 |
| Audio Data | 语音/录音 | 语音识别、语音消息 |
| Gameplay Content | 游戏内容 | 用户创建的游戏内容 |
| Customer Support | 客服数据 | 用户发起的客服请求 |
| Other User Content | 其他内容 | 用户生成的任何其他内容 |

#### Browsing History（浏览历史）
用户在 App 外查看的网页内容。

#### Search History（搜索历史）
在 App 内的搜索记录。**注意**：仅在本地处理且不发送到服务器的搜索通常不需要声明。

#### Identifiers（标识符）
| 数据类型 | 说明 | 常见场景 |
|---------|------|---------|
| User ID | 用户级 ID | 账号 ID、用户名 |
| Device ID | 设备级 ID | 广告标识符、设备 ID |

#### Purchases（购买记录）
账号或个人的购买/消费倾向。**注意**：由 Apple StoreKit 处理的支付无需声明。

#### Usage Data（使用数据）
| 数据类型 | 说明 | 常见场景 |
|---------|------|---------|
| Product Interaction | 产品交互 | 启动、点击、滚动、播放 |
| Advertising Data | 广告数据 | 用户看过的广告 |
| Other Usage Data | 其他使用数据 | 任何其他活动数据 |

#### Diagnostics（诊断）
| 数据类型 | 说明 | 常见场景 |
|---------|------|---------|
| Crash Data | 崩溃日志 | Crashlytics、Sentry |
| Performance Data | 性能数据 | 启动时间、卡顿率 |
| Other Diagnostic Data | 其他诊断 | 技术诊断数据 |

#### Surroundings（环境）
环境扫描数据（网格、平面、场景分类、图像检测）。

#### Body（身体）
手部结构/运动、头部运动。

### 每个数据类型的三个问题

勾选某个数据类型后，需回答：

**1. Is this data used for tracking?（是否用于追踪）**
- Tracking = 将该数据与第三方数据关联用于广告/广告测量，或与数据经纪商共享
- 大多数非广告 App 选 NO

**2. Is this data linked to the user's identity?（是否关联用户身份）**
- 通过账号、设备或其他方式能将数据关联到特定用户
- 无账号系统且使用匿名标识 = NO

**3. What purposes is this data collected for?（收集目的）**

| 目的 | 说明 |
|------|------|
| Third-Party Advertising | 展示第三方广告 |
| Developer's Advertising or Marketing | 自有广告/营销 |
| Analytics | 分析用户行为 |
| Product Personalization | 个性化推荐 |
| App Functionality | App 核心功能所需 |
| Other Purposes | 其他用途 |

### 可选披露（Optional Disclosure）

满足以下**全部**条件的数据类型可以不声明：
1. 不用于追踪
2. 不用于广告或营销
3. 收集仅在非核心功能的偶发场景中发生，且对用户可选
4. 收集时界面上用户姓名/账号名显著可见，且每次都需用户主动选择

**典型可以不声明的例子**：可选的反馈表单、与 App 主功能无关的客服请求。

### 最终标签预览

填写完成后，App Store 会按以下分类展示：
- **Data Used to Track You** — 用于追踪的数据
- **Data Linked to You** — 关联到用户身份的数据
- **Data Not Linked to You** — 未关联到用户身份的数据
