# 提交前审计清单

## 准备清单

### 必须准备的素材

- [ ] App 图标（1024×1024 PNG，无透明度，无圆角）
- [ ] iPhone 截图（至少 6.5" 或 6.7" 尺寸）
- [ ] iPad 截图（如支持 iPad）
- [ ] Support URL（支持页面链接）
- [ ] 隐私政策 URL（收集用户数据时必需）

### 必须填写的文本

- [ ] App Name（30 字符内）
- [ ] Subtitle（30 字符内）
- [ ] Description（4000 字符内）
- [ ] Keywords（100 字符内）
- [ ] Copyright
- [ ] 审核联系人信息

### 必须完成的选择

- [ ] Category 分类
- [ ] Age Rating 年龄分级问卷
- [ ] Content Rights 内容权利声明
- [ ] 加密声明（Info.plist 或上传文档）
- [ ] App Privacy 隐私标签（逐项数据类型声明）

---

## 代码层面必须实现的审核要求

> 以下是 App 代码中必须实现的功能，仅在 App Store Connect 配置不够，审核员会在 App 内逐项验证。

> **Review 不保证一次指出所有问题**：Apple 每次审核可能只检查部分 Guideline，上次通过的不代表下次不会被拒。每次提交前都应按此清单全量检查。

### 0. 未使用框架引用 (Guideline 2.5.1)

**要求**：App 不应引用未在主功能中使用的系统框架。import 即会被 App Review 检测。

**代码实现要点**：
- 删除功能时必须同时删除对应的 `import`、Info.plist 描述键、entitlements
- 提交前 Grep 检查：所有 `import HealthKit`、`import WeatherKit` 等框架引用是否仍有对应功能
- Info.plist 中的 `NSHealth*UsageDescription`、`NSLocation*UsageDescription` 等描述键必须与代码引用一致

### 1. 健康/营养信息引用来源 (Guideline 1.4.1)

**要求**：App 中展示的健康、营养、医疗相关信息必须附带**可点击的引用来源链接**。

**代码实现要点**：
- 所有营养分析结果页面底部必须有引用来源文本 + 可点击 `Link`（不只是纯文本书名号，Apple 要求 "links to sources"）
- AI 生成的健康建议卡片底部必须有引用来源
- AI 免责声明中必须包含具体参考文献名称
- 建议使用常量文件集中管理引用来源 URL 和文本

**关键位置**：
- 首页建议卡片、分析页面、健康洞察详情页、AI 免责声明组件
- 营养常量注释中不可引用非权威来源

### 2. 订阅页面法律链接 (Guideline 3.1.2)

**要求**：App 内的订阅购买页面必须包含**可点击的**隐私政策和用户协议链接，且位于购买按钮可视范围内。

**代码实现要点**：
- 订阅 Sheet 中购买按钮下方必须有：自动续费说明文案 + 隐私政策链接 + 用户协议链接
- 使用 `Link` 组件（不是 `Text`），确保可点击跳转浏览器
- 设置页也必须有隐私政策和用户协议入口
- 建议使用常量文件集中管理法律链接 URL（如 `LegalURLs.swift`）
- 如使用 `SubscriptionStoreView`（StoreKit 2），Apple 会自动添加条款链接；自定义 Paywall 则必须手动添加

### 3. AI/第三方数据共享明确同意 (Guideline 5.1.1(i) & 5.1.2(i))

**要求**：将用户数据发送给第三方 AI 服务前，必须获得用户**明确同意**（explicit consent）。

**代码实现要点**：
- **同意 Sheet**：中英双语（审核员是英语使用者），明确列出共享的数据类型、数据接收方（公司名）、数据用途
- **首次启动弹出**：在 `MainView.onAppear` 中检查同意状态，未同意时主动弹出同意 Sheet
- **API 层兜底**：所有 AI API 调用入口（`APIClient.request/streamRequest/streamChatRequest`）统一检查同意状态，未同意则 throw error
- **WebSocket 独立检查**：ASR 等不经过 APIClient 的路径需单独添加检查
- **UI 层优化**：AI 功能入口（对话、建议加载等）在调用前先检查，未同意时弹同意 Sheet 而非显示错误
- **设置页可撤回**：用户可在设置中查看同意详情和撤回同意
- **错误传播**：所有消费 AI API error 的 catch 路径必须处理 `consentRequired`（不能显示为"网络错误"或"获取失败"）
- 建议使用 `@AppStorage` + `UserDefaults` 管理同意状态，Service 层直接读取 `UserDefaults` 做阻断

### 4. Apple Weather 署名 (Guideline 5.2.5)

**要求**：使用 WeatherKit 时必须在 App 内显示 Apple Weather 商标（ + "Weather"）和法律归属链接。

**代码实现要点**：
- 使用天气数据的界面必须显示  Weather 署名 + 链接到 `weatherkit.apple.com/legal-attribution.html`
- 设置/关于页面必须有 Apple Weather 署名
- 使用 `apple.logo` SF Symbol（不是 `cloud.fill`），这是 Apple 商标要求
- 建议封装为可复用组件（如 `AppleWeatherAttribution`），在所有天气相关界面引用
- **仅在 App 实际使用 WeatherKit 时需要**；若已移除天气功能，此项跳过

### 5. App Description 末尾必须有法律链接

App Store Connect 中的 App 描述（Description）末尾必须添加隐私政策和用户协议 URL。这不在代码中，但属于提交审核前必做的配置。

### 6. 隐私政策必须与代码一致

**要求**：隐私政策文档中声明的数据收集类型必须与 App 实际代码一致。删除功能后必须同步更新隐私政策和 App Store Connect 的 Privacy Labels。

**常见问题**：
- 删除 HealthKit 功能后隐私政策仍提及"健康数据"
- 添加新的数据收集但隐私政策未更新
- Privacy Labels 声明了 App 实际不收集的数据类型

**检查流程**：
1. 对比代码中的 `import` 语句和 Info.plist 权限键，确认与隐私政策数据类型一致
2. 对比隐私政策声明的第三方服务与代码中实际调用的服务
3. 确认 App Store Connect Privacy Labels 与隐私政策一致

---

## Pre-Submission Code Audit（提交前代码审计）

每次提交审核前，运行以下 Grep 检查确认合规：

### 框架残留检查
```bash
# 检查是否有未使用框架的 import 残留
Grep "import HealthKit|import WeatherKit" --path <project_source>/
# 检查 Info.plist 权限键是否与实际功能一致
Grep "NSHealth|NSWeather" --path <project>.xcodeproj/
```

### Consent Flow 检查
```bash
# 确认 AI consent 阻断存在
Grep "hasAgreedToCloudAI|consentNotGranted" --path <project_source>/
# 确认 consent UI 存在
Grep "CloudAIConsentSheet" --path <project_source>/
```

### 法律链接检查
```bash
# 确认订阅页面有法律链接
Grep "LegalURLs\\.privacyPolicy|LegalURLs\\.termsOfUse" --path <project_source>/
# 确认 Link 组件（非纯 Text）
Grep "Link.*隐私政策|Link.*用户协议" --path <project_source>/
```

### 免责声明检查
```bash
# 确认洞察/AI 内容有免责声明
Grep "仅供.*参考|不构成.*建议" --path <project_source>/
```

### 隐私政策一致性检查
```bash
# 对比隐私政策中提及的数据类型与代码中的实际功能
# 手动核对：privacy-policy.md 中每个数据类型都有对应的代码功能
```

---

## ASC 文档检查

提交审核前，确认 `docs/10-app-store-connect/` 下 4 种文档齐全且与代码一致。

### 文档存在性

| 文件 | 必须存在 | 检查方式 |
|------|---------|---------|
| `privacy-policy.md` | 是 | `ls docs/10-app-store-connect/privacy-policy.md` |
| `terms-of-use.md` | 是 | `ls docs/10-app-store-connect/terms-of-use.md` |
| `support-page.md` | 是 | `ls docs/10-app-store-connect/support-page.md` |
| `market.md` | 是 | `ls docs/10-app-store-connect/market.md` |

### 隐私政策与代码一致性

1. **数据收集类型**：隐私政策中列出的每种数据类型（语音、文本、位置、健康等）必须在代码中有对应的收集逻辑；代码中收集但文档中未提及的 = 违规
2. **第三方服务**：隐私政策中列出的第三方服务名称和用途必须与代码中的实际调用一致
3. **权限声明**：Info.plist 中的权限描述键（`NS*UsageDescription`）必须与隐私政策中的权限列表匹配
4. **已移除功能**：代码中已删除的功能（如 HealthKit），隐私政策中不应再提及

### Notion 同步状态

如果使用 Notion 托管法律文档 public URL：
1. 确认 `.claude/notion-sync.local.md` 存在且配置正确
2. 确认 4 个文档都有对应的 Notion page ID
3. 使用 `/notion-page-sync` 确认 Notion 页面内容与本地文件一致

### App Store Connect 配置

以下项目需要在 ASC 后台手动验证：
- [ ] Privacy Policy URL 已填写且可访问
- [ ] App Description 末尾有隐私政策和用户协议链接
- [ ] Privacy Labels 与隐私政策一致
- [ ] 如有自定义 EULA，已在 App Information 中配置

**工具**：使用 `/update-asc-docs` 可自动审计代码并更新文档。

---

## 常见拒审原因

1. **截图与实际 App 不符** — 截图必须是真实 App 界面
2. **缺少隐私政策** — 收集任何用户数据（包括 Analytics）都需要
3. **权限说明不清** — Info.plist 中的权限描述要说明具体用途
4. **健康类 App 免责声明** — 建议在 App 内和描述中说明"仅供参考，不能替代专业医疗建议"
5. **后台 API 不可用** — 审核期间确保服务器正常运行
6. **Metadata rejected** — 名称、描述、截图不符合规范
7. **Guideline 4.2** — App 功能过于简单，建议丰富功能或做成网页
8. **登录问题** — 测试账号无效、登录流程有 bug
9. **健康/营养信息缺少引用来源** — Guideline 1.4.1 要求可点击链接，纯文本不够
10. **订阅页面缺少法律链接** — Guideline 3.1.2 要求隐私政策和用户协议在购买按钮附近
11. **AI 数据共享未获明确同意** — Guideline 5.1.1(i) 要求第三方数据共享前的 explicit consent
12. **第三方 API 商标缺失** — Guideline 5.2.5 要求 Apple Weather 等第三方服务署名

---

## 有用链接

- [App Store Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- [App Store Connect Help](https://developer.apple.com/help/app-store-connect/)
- [Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
