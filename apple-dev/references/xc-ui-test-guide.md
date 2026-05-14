# XCUITest 高级测试 Guide
<!-- SECTION MARKERS: Each "section" comment line immediately precedes the ##
     heading it labels. Use Grep("<!-- section:", file) to find sections, then
     Read(file, offset, limit) to fetch only the relevant lines. -->

XCUITest 高级用法，涵盖多屏幕用户旅程、网络层 Stub、测试数据工厂、Snapshot 测试、无障碍测试和 CI 集成。

<!-- section: 1. 多屏幕用户旅程 keywords: user journey, flow test, multi-screen, navigation test, flow object, deep link -->
## 1. 多屏幕用户旅程

### Flow Object 模式

Page Object 封装单个页面，Flow Object 封装跨页面的用户旅程。

```swift
// MARK: - Page Objects

struct LoginPage {
    let app: XCUIApplication

    var emailField: XCUIElement { app.textFields["emailTextField"] }
    var passwordField: XCUIElement { app.secureTextFields["passwordTextField"] }
    var loginButton: XCUIElement { app.buttons["loginButton"] }

    func login(email: String, password: String) {
        emailField.tap()
        emailField.typeText(email)
        passwordField.tap()
        passwordField.typeText(password)
        loginButton.tap()
    }
}

struct HomePage {
    let app: XCUIApplication

    var welcomeLabel: XCUIElement { app.staticTexts["welcomeLabel"] }
    var settingsButton: XCUIElement { app.buttons["settingsButton"] }
    var addItemButton: XCUIElement { app.buttons["addItemButton"] }

    var isDisplayed: Bool { welcomeLabel.waitForExistence(timeout: 5) }
}

struct SettingsPage {
    let app: XCUIApplication

    var logoutButton: XCUIElement { app.buttons["logoutButton"] }
    var notificationsToggle: XCUIElement { app.switches["notificationsSwitch"] }
}

// MARK: - Flow Object

struct OnboardingFlow {
    let app: XCUIApplication
    let loginPage: LoginPage
    let homePage: HomePage

    init(app: XCUIApplication) {
        self.app = app
        self.loginPage = LoginPage(app: app)
        self.homePage = HomePage(app: app)
    }

    /// 完成登录并验证到达首页
    @discardableResult
    func completeLogin(email: String = "test@example.com",
                       password: String = "password123") -> HomePage {
        loginPage.login(email: email, password: password)
        XCTAssertTrue(homePage.isDisplayed, "Should navigate to home after login")
        return homePage
    }
}

// MARK: - Test

final class OnboardingUITests: XCTestCase {
    var app: XCUIApplication!
    var flow: OnboardingFlow!

    override func setUp() {
        super.setUp()
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["--uitesting"]
        app.launch()
        flow = OnboardingFlow(app: app)
    }

    func testFullOnboardingJourney() {
        let homePage = flow.completeLogin()
        XCTAssertTrue(homePage.welcomeLabel.exists)
    }
}
```

### LaunchArguments / LaunchEnvironment 控制初始状态

```swift
// 测试中设置
app.launchArguments = [
    "--uitesting",           // 标记 UI 测试模式
    "--skip-onboarding",     // 跳过引导页
    "--reset-state",         // 重置 app 状态
]

app.launchEnvironment = [
    "MOCK_API": "true",              // 启用 mock 网络
    "INITIAL_SCREEN": "settings",    // 直接打开指定页面
    "USER_TIER": "premium",          // 模拟付费用户
]

// App 中读取
struct AppConfig {
    static var isUITesting: Bool {
        CommandLine.arguments.contains("--uitesting")
    }

    static var mockAPI: Bool {
        ProcessInfo.processInfo.environment["MOCK_API"] == "true"
    }

    static var initialScreen: String? {
        ProcessInfo.processInfo.environment["INITIAL_SCREEN"]
    }
}
```

### App State 等待

```swift
// 等待 app 达到指定状态
let app = XCUIApplication()
app.launch()

// 等待 app 进入运行状态（launch 后默认就是）
XCTAssertTrue(app.wait(for: .runningForeground, timeout: 10))

// 等待 app 进入后台（如触发系统弹窗后）
// app.wait(for: .runningBackground, timeout: 5)
```

### 深链接测试

```swift
func testDeepLinkOpensCorrectScreen() {
    let app = XCUIApplication()
    app.launch()

    // 使用 open(URL) 模拟深链接
    let deepLink = URL(string: "myapp://item/12345")!
    app.open(deepLink)

    // 验证到达目标页面
    let itemTitle = app.staticTexts["Item #12345"]
    XCTAssertTrue(itemTitle.waitForExistence(timeout: 5))
}
```

<!-- section: 2. 网络层 Stub keywords: network stub, URLProtocol, mock server, network test, fixture, offline -->
## 2. 网络层 Stub

### URLProtocol 子类拦截请求

```swift
final class MockURLProtocol: URLProtocol {
    // 存储 mock 响应的字典
    static var mockResponses: [String: (Data, HTTPURLResponse)] = [:]

    override class func canInit(with request: URLRequest) -> Bool {
        // 拦截所有请求
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        request
    }

    override func startLoading() {
        guard let url = request.url,
              let (data, response) = MockURLProtocol.mockResponses[url.path] else {
            // 无 mock → 返回 404
            let response = HTTPURLResponse(url: request.url!, statusCode: 404,
                                           httpVersion: nil, headerFields: nil)!
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocolDidFinishLoading(self)
            return
        }

        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }

    override func stopLoading() {}
}

// 注册（在 App 的 mock 模式中）
if AppConfig.mockAPI {
    let config = URLSessionConfiguration.default
    config.protocolClasses = [MockURLProtocol.self]
    // 使用此 config 创建 URLSession
}
```

### LaunchEnvironment 切换 Mock 模式

```swift
// 测试端
func setUp() {
    app.launchEnvironment["MOCK_API"] = "true"
    app.launchEnvironment["MOCK_SCENARIO"] = "happy_path"  // 或 "error", "empty", "slow"
    app.launch()
}

// App 端
enum MockScenario: String {
    case happyPath = "happy_path"
    case error = "error"
    case empty = "empty"
    case slow = "slow"
}

func configureMocks(scenario: MockScenario) {
    switch scenario {
    case .happyPath:
        MockURLProtocol.mockResponses["/api/items"] = (
            loadFixture("items_success.json"),
            HTTPURLResponse(url: URL(string: "https://api.example.com/api/items")!,
                          statusCode: 200, httpVersion: nil,
                          headerFields: ["Content-Type": "application/json"])!
        )
    case .error:
        MockURLProtocol.mockResponses["/api/items"] = (
            loadFixture("error_500.json"),
            HTTPURLResponse(url: URL(string: "https://api.example.com/api/items")!,
                          statusCode: 500, httpVersion: nil, headerFields: nil)!
        )
    case .empty:
        MockURLProtocol.mockResponses["/api/items"] = (
            "[]".data(using: .utf8)!,
            HTTPURLResponse(url: URL(string: "https://api.example.com/api/items")!,
                          statusCode: 200, httpVersion: nil,
                          headerFields: ["Content-Type": "application/json"])!
        )
    case .slow:
        // 延迟通过 URLProtocol 的 startLoading 中添加 sleep 实现
        break
    }
}
```

### JSON Fixture 文件管理

```
MyAppUITests/
├── Fixtures/
│   ├── items_success.json
│   ├── items_empty.json
│   ├── user_profile.json
│   ├── error_401.json
│   └── error_500.json
```

```swift
func loadFixture(_ name: String) -> Data {
    let bundle = Bundle(for: type(of: self))
    let url = bundle.url(forResource: name.replacingOccurrences(of: ".json", with: ""),
                         withExtension: "json")!
    return try! Data(contentsOf: url)
}
```

### 错误场景模拟

```swift
func testNetworkError_ShowsRetryButton() {
    app.launchEnvironment["MOCK_SCENARIO"] = "error"
    app.launch()

    // 验证错误状态 UI
    XCTAssertTrue(app.staticTexts["Something went wrong"].waitForExistence(timeout: 5))
    XCTAssertTrue(app.buttons["Retry"].exists)

    // 切换到成功 → 点击 Retry
    // 注意：无法在运行中切换 mock，需要通过 app 内部逻辑处理
}

func testOfflineMode() {
    app.launchEnvironment["MOCK_SCENARIO"] = "offline"
    app.launch()

    XCTAssertTrue(app.staticTexts["No internet connection"].waitForExistence(timeout: 5))
}
```

<!-- section: 3. 测试数据工厂 keywords: test data, fixture, factory, builder, seed, state isolation, resetAuthorizationStatus -->
## 3. 测试数据工厂

### Builder Pattern 构造测试数据

```swift
struct ItemBuilder {
    private var name = "Test Item"
    private var price: Double = 9.99
    private var category = "General"
    private var isFavorite = false

    func withName(_ name: String) -> ItemBuilder {
        var copy = self
        copy.name = name
        return copy
    }

    func withPrice(_ price: Double) -> ItemBuilder {
        var copy = self
        copy.price = price
        return copy
    }

    func withCategory(_ category: String) -> ItemBuilder {
        var copy = self
        copy.category = category
        return copy
    }

    func asFavorite() -> ItemBuilder {
        var copy = self
        copy.isFavorite = true
        return copy
    }

    func build() -> Item {
        Item(name: name, price: price, category: category, isFavorite: isFavorite)
    }
}

// 使用
let item = ItemBuilder()
    .withName("Premium Widget")
    .withPrice(49.99)
    .asFavorite()
    .build()
```

### SwiftData In-Memory Container

```swift
@MainActor
func createTestContainer(with items: [Item] = []) -> ModelContainer {
    let config = ModelConfiguration(isStoredInMemoryOnly: true)
    let container = try! ModelContainer(for: Item.self, configurations: config)

    for item in items {
        container.mainContext.insert(item)
    }
    try! container.mainContext.save()

    return container
}

// 在 UI 测试中通过 LaunchEnvironment 传递数据库路径
// 或使用 --reset-state 标志在 app 启动时清空数据
```

### resetAuthorizationStatus 重置权限

```swift
func testCameraPermission_WhenDenied_ShowsSettingsPrompt() {
    let app = XCUIApplication()
    // 重置相机权限到"未决定"状态
    app.resetAuthorizationStatus(for: .camera)
    app.launch()

    app.buttons["Take Photo"].tap()

    // 系统权限弹窗
    let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
    let denyButton = springboard.buttons["Don't Allow"]
    if denyButton.waitForExistence(timeout: 3) {
        denyButton.tap()
    }

    // 验证 app 显示引导
    XCTAssertTrue(app.staticTexts["Camera access required"].waitForExistence(timeout: 3))
}
```

**支持的 XCUIProtectedResource**:
- `.camera`
- `.microphone`
- `.photos`
- `.contacts`
- `.calendar`
- `.location`
- `.health`
- `.bluetooth`

### App 状态隔离

```swift
final class CleanStateUITests: XCTestCase {
    var app: XCUIApplication!

    override func setUp() {
        super.setUp()
        continueAfterFailure = false

        app = XCUIApplication()
        app.launchArguments = [
            "--uitesting",
            "--reset-state",  // App 启动时清空 UserDefaults + 数据库
        ]
    }

    // 每个测试都从干净状态开始
    func testAddFirstItem() {
        app.launch()
        XCTAssertTrue(app.staticTexts["No items yet"].exists)
        // ...
    }
}

// App 端实现
func application(_ application: UIApplication,
                 didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
    if CommandLine.arguments.contains("--reset-state") {
        // 清空 UserDefaults
        let domain = Bundle.main.bundleIdentifier!
        UserDefaults.standard.removePersistentDomain(forName: domain)

        // 清空 SwiftData（删除 .store 文件）
        let storeURL = URL.applicationSupportDirectory.appending(path: "default.store")
        try? FileManager.default.removeItem(at: storeURL)
    }
    return true
}
```

<!-- section: 4. Snapshot / 视觉回归测试 keywords: snapshot test, visual regression, screenshot comparison, swift-snapshot-testing, tolerance -->
## 4. Snapshot / 视觉回归测试

### swift-snapshot-testing 集成

```swift
// Package.swift 依赖
// .package(url: "https://github.com/pointfreeco/swift-snapshot-testing", from: "1.15.0")

import XCTest
import SnapshotTesting

final class SettingsViewSnapshotTests: XCTestCase {

    func testSettingsView_Default() {
        let view = SettingsView()
        assertSnapshot(of: view, as: .image(layout: .device(config: .iPhone13Pro)))
    }

    func testSettingsView_DarkMode() {
        let view = SettingsView()
            .environment(\.colorScheme, .dark)
        assertSnapshot(of: view, as: .image(layout: .device(config: .iPhone13Pro)))
    }

    func testSettingsView_LargeText() {
        let view = SettingsView()
            .environment(\.sizeCategory, .accessibilityExtraExtraLarge)
        assertSnapshot(of: view, as: .image(layout: .device(config: .iPhone13Pro)))
    }
}
```

### 多设备矩阵

```swift
final class HomeViewSnapshotTests: XCTestCase {

    let devices: [(String, ViewImageConfig)] = [
        ("iPhoneSE", .iPhoneSe),
        ("iPhone15Pro", .iPhone13Pro),
        ("iPadPro11", .iPadPro11),
    ]

    func testHomeView_AllDevices() {
        let view = HomeView()

        for (name, config) in devices {
            assertSnapshot(
                of: view,
                as: .image(layout: .device(config: config)),
                named: name
            )
        }
    }
}
```

### Dynamic Type 矩阵

```swift
let sizeCategories: [(String, ContentSizeCategory)] = [
    ("XS", .extraSmall),
    ("Default", .medium),
    ("XL", .extraLarge),
    ("AXXL", .accessibilityExtraExtraLarge),
]

func testItemRow_AllSizes() {
    let item = ItemBuilder().withName("Test").build()

    for (name, size) in sizeCategories {
        let view = ItemRow(item: item)
            .environment(\.sizeCategory, size)
        assertSnapshot(
            of: view,
            as: .image(layout: .sizeThatFits),
            named: name
        )
    }
}
```

### Tolerance 配置与 CI 更新流程

```swift
// 设置像素容差（应对渲染差异）
assertSnapshot(
    of: view,
    as: .image(layout: .device(config: .iPhone13Pro),
               perceptualPrecision: 0.98),  // 允许 2% 感知差异
    named: "settings"
)

// CI 中更新 snapshot：
// 1. 设置环境变量：SNAPSHOT_TESTING_RECORD=true
// 2. 运行测试 → 生成新的参考图片
// 3. 审查 diff，提交更新后的 __Snapshots__ 目录
```

```bash
# 录制新 snapshot
SNAPSHOT_TESTING_RECORD=true xcodebuild test \
    -scheme MyApp \
    -destination 'platform=iOS Simulator,name=iPhone 15 Pro'
```

### XCTAttachment 截图保存

```swift
// XCUITest 中手动截图
func testCheckoutFlow() {
    // ... 操作步骤 ...

    // 保存当前屏幕截图（附加到测试结果）
    let screenshot = app.screenshot()
    let attachment = XCTAttachment(screenshot: screenshot)
    attachment.name = "Checkout - Payment Screen"
    attachment.lifetime = .keepAlways  // .deleteOnSuccess 只在失败时保留
    add(attachment)
}
```

<!-- section: 5. 无障碍测试 keywords: accessibility, audit, VoiceOver, a11y test, performAccessibilityAudit, accessibilityIdentifier -->
## 5. 无障碍测试

### performAccessibilityAudit 自动审计

```swift
func testAccessibility_HomeScreen() throws {
    let app = XCUIApplication()
    app.launch()

    // 自动检查常见无障碍问题
    try app.performAccessibilityAudit()
}

// 指定审计类型
func testAccessibility_SpecificChecks() throws {
    let app = XCUIApplication()
    app.launch()

    try app.performAccessibilityAudit(for: [
        .dynamicType,        // Dynamic Type 支持
        .contrast,           // 色彩对比度
        .elementDetection,   // 元素可检测性
        .hitRegion,          // 触控区域大小
        .sufficientElementDescription,  // 元素描述充分性
    ])
}
```

### 过滤已知问题

```swift
func testAccessibility_FilterKnownIssues() throws {
    let app = XCUIApplication()
    app.launch()

    try app.performAccessibilityAudit { issue in
        // 返回 true = 忽略此问题
        // 返回 false = 报告此问题

        // 忽略第三方 SDK 的元素
        if let element = issue.element,
           element.identifier.hasPrefix("thirdParty_") {
            return true
        }

        // 忽略特定类型的问题
        if issue.auditType == .contrast {
            // 已知设计要求低对比度的装饰元素
            return issue.element?.identifier == "decorativeBackground"
        }

        return false  // 报告其他所有问题
    }
}
```

### accessibilityIdentifier 策略

```swift
// ✅ 有意义的标识符命名
Text("Welcome")
    .accessibilityIdentifier("welcomeLabel")

Button("Add Item") { }
    .accessibilityIdentifier("addItemButton")

// ✅ 列表项使用唯一标识符
ForEach(items) { item in
    ItemRow(item: item)
        .accessibilityIdentifier("itemRow_\(item.id)")
}

// ❌ 避免：用自动生成的索引
// .accessibilityIdentifier("cell_0")  // 顺序变化会破坏测试

// 集中管理标识符
enum AccessibilityID {
    enum Login {
        static let emailField = "login_emailField"
        static let passwordField = "login_passwordField"
        static let submitButton = "login_submitButton"
    }

    enum Home {
        static let welcomeLabel = "home_welcomeLabel"
        static let addButton = "home_addButton"
        static func itemRow(_ id: String) -> String { "home_itemRow_\(id)" }
    }
}
```

### VoiceOver 手动测试 Checklist

以下项目无法自动化，需要设备上手动验证：

- [ ] 所有可交互元素都能被 VoiceOver 聚焦
- [ ] 聚焦顺序符合逻辑阅读顺序
- [ ] 图片有描述性 accessibilityLabel（非文件名）
- [ ] 按钮的 accessibilityLabel 描述操作（"删除项目"而非"红色按钮"）
- [ ] 列表项的 accessibilityLabel 包含完整信息
- [ ] 自定义手势有 accessibilityAction 替代
- [ ] 页面切换时 VoiceOver 焦点移到正确位置
- [ ] 错误提示通过 accessibilityAnnouncement 朗读

<!-- section: 6. CI 集成与优化 keywords: CI, xcodebuild, parallel testing, result bundle, xcresulttool, retry, simulator -->
## 6. CI 集成与优化

### xcodebuild test 命令

```bash
# 运行所有 UI 测试
xcodebuild test \
    -scheme MyApp \
    -destination 'platform=iOS Simulator,name=iPhone 15 Pro,OS=18.0' \
    -testPlan UITests \
    -resultBundlePath ./TestResults.xcresult

# 只运行指定测试类
xcodebuild test \
    -scheme MyApp \
    -destination 'platform=iOS Simulator,name=iPhone 15 Pro' \
    -only-testing:MyAppUITests/LoginUITests

# 跳过指定测试
xcodebuild test \
    -scheme MyApp \
    -destination 'platform=iOS Simulator,name=iPhone 15 Pro' \
    -skip-testing:MyAppUITests/SlowUITests
```

### Parallel Testing

```bash
# 启用并行测试（多个 Simulator 实例）
xcodebuild test \
    -scheme MyApp \
    -destination 'platform=iOS Simulator,name=iPhone 15 Pro' \
    -parallel-testing-enabled YES \
    -parallel-testing-worker-count 4

# 注意事项：
# - 每个 worker 使用独立的 Simulator clone
# - 测试必须完全隔离（无共享状态）
# - 每个测试 setUp 时使用 --reset-state
```

### Test Plan 配置

```
MyApp.xctestplan 中配置：
- Configurations: 可定义多个配置（语言、地区、设备）
- Test Targets: 选择要运行的测试 target
- Arguments: 设置 launchArguments 和 environment
- Options:
  - Code Coverage: 启用/禁用
  - Execution Order: Random / Alphabetical
  - Language & Region: 指定测试语言
  - Localization Screenshots: 自动截图
```

### Result Bundle 解析

```bash
# 查看测试结果摘要
xcresulttool get --format human-readable --path ./TestResults.xcresult

# 导出为 JSON
xcresulttool get --format json --path ./TestResults.xcresult > results.json

# 提取失败截图
xcresulttool export --path ./TestResults.xcresult \
    --output-path ./FailureScreenshots \
    --type attachments

# 查看测试覆盖率
xccov view --report --json ./TestResults.xcresult > coverage.json
```

### 失败截图自动收集

```swift
// 在测试基类中自动保存失败截图
class BaseUITestCase: XCTestCase {
    var app: XCUIApplication!

    override func setUp() {
        super.setUp()
        continueAfterFailure = false
        app = XCUIApplication()
    }

    override func tearDown() {
        // 测试失败时自动保存截图
        if testRun?.hasSucceeded == false {
            let screenshot = XCUIScreen.main.screenshot()
            let attachment = XCTAttachment(screenshot: screenshot)
            attachment.name = "Failure - \(name)"
            attachment.lifetime = .keepAlways
            add(attachment)
        }
        super.tearDown()
    }
}
```

### Retry 失败测试

```bash
# xcodebuild 内置 retry（Xcode 13+）
xcodebuild test \
    -scheme MyApp \
    -destination 'platform=iOS Simulator,name=iPhone 15 Pro' \
    -retry-tests-on-failure \
    -test-iterations 3  # 最多重试 3 次
```

```
# Test Plan 中配置 retry：
# Test Repetition Mode:
#   - Retry on Failure: 失败时重试
#   - Maximum Repetitions: 3
#   - Stop after failure: 第一次成功就停
```

### CI 环境 Simulator 管理

```bash
# 列出可用 Simulator
xcrun simctl list devices available

# 创建指定型号 Simulator
xcrun simctl create "CI iPhone" "iPhone 15 Pro" "iOS 18.0"

# 启动 Simulator（headless，CI 环境）
xcrun simctl boot "CI iPhone"

# 清除 Simulator 数据
xcrun simctl erase "CI iPhone"

# 删除不用的 Simulator
xcrun simctl delete unavailable

# 安装 app（用于调试 CI 问题）
xcrun simctl install "CI iPhone" ./Build/Products/Debug-iphonesimulator/MyApp.app
```

## 参考

- [Apple: Testing Your Apps in Xcode](https://developer.apple.com/documentation/xcode/testing-your-apps-in-xcode)
- [Apple: XCUIApplication](https://developer.apple.com/documentation/xctest/xcuiapplication)
- [Apple: Accessibility Audit](https://developer.apple.com/documentation/xctest/xcuiapplication/performaccessibilityaudit(for:_:))
- [pointfreeco/swift-snapshot-testing](https://github.com/pointfreeco/swift-snapshot-testing)
- [WWDC23: Fix failures faster with Xcode test reports](https://developer.apple.com/videos/play/wwdc2023/10175/)

### 相关 Skill

- `/testing-guide` — Unit Test、Mock/DI、TDD 基础、Page Object 入门
- `/profiling` — 性能测试（XCTMetric、XCTOSSignpostMetric、XCTHitchMetric）

## XCUITest API Reference (vendored from vabole/apple-skills)

_Inline attribution: vendor 自 vabole/apple-skills v1.0.10 `skills/xcuitest/` (MIT, (c) 2026 Ilia Abolhasani, vendored 2026-05-14). 与本仓 above 节互补：本仓给高级 XCUITest 工作流（E2E、network stub、snapshot、a11y、CI）；下方为 element queries / waiting / Swift 6 @MainActor / launch arguments / screenshots 的 API ref，grepable。冲突时本仓骨架为准。_

### xctest-index

<!-- Content from /tmp/apple-skills-research/skills/xcuitest/xctest-index.md -->

This is the index for the XCUITest API documentation. Refer to the subsections below for individual class/framework API details.

**Topics covered:**
- `XCUIApplication` — launching, monitoring, terminating test applications
- `XCUIElement` — querying and interacting with UI elements
- `XCUIElementQuery` — search criteria for identifying UI elements
- `XCUICoordinate` — screen locations relative to UI elements
- `XCUIProtectedResource` — authorization for protected resources
- `XCUIScreenshot` — capturing screenshots of UI state

### xcuielementquery

**Available on:** iOS, iPadOS, Mac Catalyst, macOS, tvOS, visionOS, watchOS, Xcode 16.3+

> An object that defines the search criteria a test uses to identify UI elements.

```swift
@MainActor class XCUIElementQuery
```

Use element queries to find UI elements in your app that you interact with in the tests, to test for the presence of expected elements, or to discover elements to test their values.

For example, this test uses an element query to find the "Add Book" button, and after clicking the button, checks that there is one button in an outline view cell titled "Untitled Book". If the test cannot find the "Add Book" button, or there is not one "Untitled Book" cell, then the test fails.

```swift
@MainActor
func testClickingAddCreatesAnUntitledBook() throws {
    let app = XCUIApplication()
    app.launch()
    let list = app.windows["Reading Journal"]
    list.toolbars.children(matching: .button)["Add Book"].click()
    XCTAssertEqual(list.outlines["Sidebar"].cells.containing(.button, identifier:"Untitled Book").count, 1)
}
```

**Creating new queries:**
- `children(matching:)` — Returns a new query that matches all direct children of the requested type.
- `descendants(matching:)` — Returns a new query that matches all descendants of the requested type.
- `containing(_:)` — Returns a new query that matches elements containing a descendant that meets the logical conditions of the provided predicate.
- `containing(_:identifier:)` — Returns a new query that matches elements that contain a descendant of the requested type and an identifying property that matches a provided identifier.
- `matching(identifier:)` — Returns a new query that matches elements that have an identifying property that matches a provided identifier.
- `matching(_:)` — Returns a new query that matches elements that meet the logical conditions of the provided predicate.
- `matching(_:identifier:)` — Returns a new query that matches elements of the requested type and have an identifying property that matches a provided identifier.

**Accessing matched elements:**
- `allElementsBoundByAccessibilityElement` — Immediately evaluates the query and returns an array of elements bound to the resulting accessibility elements.
- `allElementsBoundByIndex` — Immediately evaluates the query and returns an array of elements bound by the index of each result.
- `count` — Evaluates the query and returns the number of elements that match.
- `element` — The query's single matching element.
- `element(boundBy:)` — Uses an index into the query's results to determine which underlying accessibility element to use.
- `element(matching:)` — Matches the predicate.
- `element(matching:identifier:)` — Matches the provided element type and identifier.
- `subscript(_:)` — Returns a descendant element that matches a provided identifier.
- `element(at:)` — Returns an element that resolves to the index into the query's result set.

**Debugging element queries:**
- `debugDescription` — Provides debugging information about the query.

### xcuielement

**Available on:** iOS, iPadOS, Mac Catalyst, macOS, tvOS, visionOS, watchOS, Xcode 16.3+

> A UI element in an application.

```swift
@MainActor class XCUIElement
```

In macOS and iPadOS 15 and later, `XCUIElement` provides a way to test your app with keyboard and mouse interactions, such as typing, clicking, scrolling, and moving and pausing the pointer. In iOS, `XCUIElement` provides a way to test your app with gestures, such as tapping, swiping, pinching, and rotating.

**Querying element state:**
- `waitForExistence(timeout:)` — Waits the specified amount of time for an element to exist.
- `waitForNonExistence(timeout:)` — Waits the specified amount of time for an element to no longer exist.
- `wait(for:toEqual:timeout:)` — Waits a specified amount of time for a property value to equal a specified value.
- `exists` — Determines if the element exists.
- `isHittable` — Determines if the system can compute a hit point for the element.
- `debugDescription` — Provides debugging information about the element.

**Querying descendant elements:**
- `children(matching:)` — Returns a query for all direct children of the element matching the type you specify.
- `descendants(matching:)` — Returns a query for all descendants of the element matching the type you specify.

**Typing text:**
- `typeText(_:)` — Types a string into the element.

**Combining keystrokes:**
- `typeKey(_:modifierFlags:)` — Types a single key from the XCUIKeyboardKey enumeration with the specified modifier flags.
- `perform(withKeyModifiers:block:)` — Executes a block of code while holding a combination keystroke.
- `XCUIElement.KeyModifierFlags` — Flags for simulating combination keystrokes with keys, such as Control, Option, Shift, and Command.

**Moving the pointer:**
- `hover()` — Moves the pointer over the element.

**Clicking:**
- `click()` — Sends a click event to a hittable point computed for the element.
- `click(forDuration:thenDragTo:)` — Clicks and holds an element for a duration you specify, then drags it to another element.
- `doubleClick()` — Sends a double-click event to a hittable point the system computes for the element.
- `rightClick()` — Sends a Control-click event to a hittable point the system computes for the element.

**Scrolling:**
- `scroll(byDeltaX:deltaY:)` — Scrolls the view by the number of x and y pixels you specify.

**Tapping and pressing:**
- `tap()` — Sends a tap event to a hittable point computed for the element.
- `doubleTap()` — Sends a double-tap event to a hittable point computed for the element.
- `press(forDuration:)` — Sends a press-and-hold gesture to a hittable point computed for the element.
- `press(forDuration:thenDragTo:)` — Initiates a press-and-hold gesture, then drags to another element.

**Tapping multiple times:**
- `twoFingerTap()` — Sends a two-finger tap event to a hittable point computed for the element.
- `tap(withNumberOfTaps:numberOfTouches:)` — Sends one or more taps with one or more touch points.

**Performing gestures:**
- `swipeLeft()`, `swipeLeft(velocity:)` — Sends a swipe-left gesture.
- `swipeRight()`, `swipeRight(velocity:)` — Sends a swipe-right gesture.
- `swipeUp()`, `swipeUp(velocity:)` — Sends a swipe-up gesture.
- `swipeDown()`, `swipeDown(velocity:)` — Sends a swipe-down gesture.
- `pinch(withScale:velocity:)` — Sends a pinching gesture with two touches.
- `rotate(_:withVelocity:)` — Sends a rotation gesture with two touches.
- `XCUIGestureVelocity` — A value that describes how fast a gesture moves across the screen, in pixels per second.

**Interacting with sliders:**
- `normalizedSliderPosition` — Returns the position of the slider's indicator as a normalized value.
- `adjust(toNormalizedSliderPosition:)` — Manipulates the UI to change the slider value to a new normalized position.
- `adjust(toPickerWheelValue:)` — Changes the value that a picker wheel displays.

**Calculating coordinates:**
- `coordinate(withNormalizedOffset:)` — Creates and returns a new coordinate with a normalized offset.

**Supporting types:**
- `XCUIElement.ElementType` — The types of UI elements (button, cell, textField, etc.).
- `XCUIElement.SizeClass` — The user interface size classes you can inspect in a UI test.
- `XCUIElement.AttributeName` — A set of string constants serving as keys for storing element attributes.

### xcuiapplication

**Available on:** iOS, iPadOS, Mac Catalyst, macOS, tvOS, visionOS, watchOS, Xcode 16.3+

> A proxy that can launch, monitor, and terminate a test application.

```swift
@MainActor class XCUIApplication
```

Use this class to launch, monitor, and terminate your app in a UI test. Use `wait(for:timeout:)` to launch your app and wait for it to reach an expected state before you check test conditions.

**Creating an application proxy:**
- `init()` — Creates a proxy for the application configured as the Target Application in Xcode's target settings.
- `init(bundleIdentifier:)` — Creates a proxy for the application with the specified bundle identifier.
- `init(url:)` — Creates a proxy for the application at the specified file system URL.

**Launching the application:**
- `launch()` — Launches the application.
- `launchArguments` — The arguments passed to the application on launch.
- `launchEnvironment` — The environment variables passed to the application on launch.
- `open(_:)` — Launches the application by URL.

**Activating and terminating:**
- `activate()` — Activates the application.
- `terminate()` — Terminates any running instance of the application.
- `state` — The most recent state of the application.
- `XCUIApplication.State` — The possible states of an application during UI testing.
- `wait(for:timeout:)` — Waits for the application to reach the specified state or timeout.

**Resetting authorization status:**
- `resetAuthorizationStatus(for:)` — Resets the authorization status for a protected resource.
- `XCUIProtectedResource` — A system resource that requires user authorization to access.

**Performing an accessibility audit:**
- `performAccessibilityAudit(for:_:)` — Performs an accessibility audit on specified elements.
- `XCUIAccessibilityAuditType` — The types of accessibility audits available.
- `XCUIAccessibilityAuditIssue` — An issue found during an accessibility audit.

### xcuiautomation-index

<!-- Content from /tmp/apple-skills-research/skills/xcuitest/xcuiautomation-index.md -->

This is the index for the XCUIAutomation framework API documentation. It covers all XCUITest classes referenced above including `XCUIApplication`, `XCUIElement`, `XCUIElementQuery`, `XCUICoordinate`, `XCUIProtectedResource`, and `XCUIScreenshot`.

### xcuicoordinate

**Available on:** iOS, iPadOS, Mac Catalyst, macOS, visionOS, watchOS, Xcode 16.3+

> A location on screen relative to a UI element.

```swift
@MainActor class XCUICoordinate
```

Coordinates are dynamic, like the elements to which they refer, and may compute different screen locations at different times, or be invalid if the element they reference does not exist.

**Getting coordinate properties:**
- `referencedElement` — The element that the coordinate is based on, either directly or through the coordinate from which it was derived.
- `screenPoint` — The dynamically computed value of the coordinate's location on screen.

**Moving the pointer:**
- `hover()` — Moves the pointer to the coordinate.

**Clicking:**
- `click()` — Sends a click event at the coordinate.
- `click(forDuration:thenDragTo:)` — Clicks and holds for a duration you specify, then drags to the other coordinate.
- `doubleClick()` — Sends a double-click event at the coordinate.
- `rightClick()` — Sends a Control-click event at the coordinate.

**Scrolling:**
- `scroll(byDeltaX:deltaY:)` — Scrolls the view by the number of x and y pixels you specify.

**Tapping and pressing:**
- `tap()` — Sends a tap event at the coordinate.
- `doubleTap()` — Sends a double-tap event at the coordinate.
- `press(forDuration:)` — Initiates a press-and-hold gesture at the coordinate.
- `press(forDuration:thenDragTo:)` — Initiates a press-and-hold gesture, then drags to another coordinate.

**Performing gestures:**
- `swipeLeft()`, `swipeLeft(velocity:)`, `swipeRight()`, `swipeRight(velocity:)`, `swipeUp()`, `swipeUp(velocity:)`, `swipeDown()`, `swipeDown(velocity:)` — Send swipe gestures at the coordinate.

**Creating relative coordinates:**
- `withOffset(_:)` — Creates a new coordinate with an absolute offset in points from the original coordinate.

### xcuiprotectedresource

**Available on:** iOS 13.4+, iPadOS 13.4+, Mac Catalyst 13.4+, macOS 10.15.4+, tvOS 13.4+, visionOS 1.0+, watchOS 6.2+, Xcode 16.3+

> A system resource that requires user authorization to access.

```swift
enum XCUIProtectedResource
```

**Protected resource cases:**
- `location` — Location Services
- `userTracking` — Tracking data
- `contacts` — Contacts data
- `calendar` — Calendar data
- `reminders` — Reminders data
- `photos` — Photos
- `bluetooth` — Bluetooth utilization
- `localNetwork` — Local network devices
- `microphone` — Microphone
- `camera` — Camera
- `health` — Health data
- `homeKit` — Home data
- `mediaLibrary` — Media library
- `keyboardNetwork` — Keyboard network
- `systemRootDirectory` — System root directory
- `userDesktopDirectory` — Desktop directory
- `userDocumentsDirectory` — Documents directory
- `userDownloadsDirectory` — Downloads directory
- `focus` — Focus status
- `removableVolumes` — Removable volumes
- `networkVolumes` — Network volumes
- `appleEvents` — Apple Events

**Resetting authorization status:**
Use `XCUIApplication.resetAuthorizationStatus(for:)` to reset the authorization status for a protected resource.

### xcuiscreenshot

**Available on:** iOS, iPadOS, Mac Catalyst, macOS, tvOS, visionOS, watchOS, Xcode 16.3+

> A captured image of a screen, app, or UI element state.

```swift
@MainActor class XCUIScreenshot
```

Screenshots capture the current UI state of classes that conform to `XCUIScreenshotProviding`, such as `XCUIScreen` and `XCUIElement`.

```swift
func testTakeScreenshots() {
    // Take a screenshot of the current device's main screen.
    let mainScreenScreenshot = XCUIScreen.main.screenshot()

    // Take a screenshot of an app's first window.
    let app = XCUIApplication()
    app.launch()
    let windowScreenshot = app.windows.firstMatch.screenshot()
}
```

**Screenshot representations:**
- `image` — A representation of the screenshot as a platform-native image object.
- `pngRepresentation` — A representation of the screenshot as PNG image data.

**Attaching screenshots to tests (XCTest):**
Create an attachment using `XCTAttachment(screenshot:)` or `XCTAttachment(screenshot:quality:)`, then add it to the test using `XCTActivity.add(_:)`.

### patterns

<!-- Content from /tmp/apple-skills-research/skills/xcuitest/patterns.md -->

Common XCUITest patterns and best practices for writing robust UI tests.

**Waiting for elements:** Always use `waitForExistence(timeout:)` before interacting with elements rather than relying on immediate availability. This prevents flaky tests.

```swift
let button = app.buttons["Submit"]
XCTAssertTrue(button.waitForExistence(timeout: 5))
button.tap()
```

**Checking element existence:** Use `exists` for simple checks, but prefer `waitForExistence` when you need the element to appear as a result of an action.

**Chaining queries:** Build complex queries by chaining `children(matching:)`, `descendants(matching:)`, and `containing(_:identifier:)` methods.

```swift
let cell = app.tables.cells.containing(.textField, identifier: "Name")
cell.textFields["Name"].tap()
```

**Swift 6 @MainActor:** XCUITest classes are `@MainActor`. Write all test methods as `@MainActor` functions or mark the whole test class as `@MainActor`.

```swift
@MainActor
class MyTests {
    @Test func example() {
        let app = XCUIApplication()
        app.launch()
        // ...
    }
}
```

**Launch arguments and environment:** Pass test-specific configuration via `launchArguments` and `launchEnvironment`.

```swift
app.launchArguments = ["--reset-state"]
app.launchEnvironment = ["API_BASE_URL": "https://test.example.com"]
app.launch()
```


### xctest-index (API Index)

**Full XCTest API Index — extracted from Apple DocC JSON.**

**Test Cases and Test Methods:**
- `XCTestCase` — Base class for all test cases
- `setUp()` / `setUpWithError()` — Run before each test method
- `tearDown()` / `tearDownWithError()` — Run after each test method
- `addTeardownBlock(() throws -> Void)` — Deferred teardown closures
- `continueAfterFailure` — Whether to stop on first failure
- `executionTimeAllowance` — Time limit per test

**Measuring Performance:**
- `measure(_:)` / `measure(metrics:block:)` — Block-based performance measurement
- `startMeasuring()` / `stopMeasuring()` — Manual measurement boundaries
- `defaultPerformanceMetrics` / `defaultMetrics` — Built-in metrics
- `XCTPerformanceMetric` — Metric type (wallClockTime, custom)

**Asynchronous Test Expectations:**
- `expectation(description:)` — Basic expectation
- `expectation(forNotification:name:object:handler:)` — NSNotification expectation
- `expectation(for:KVOObject keyPath:expectedValue:)` — KVO expectation
- `expectation(that: KeyPath<K,V> willEqual:)` — KeyPath expectation
- `fulfillment(of:timeout:enforceOrder:)` — Async/await based wait
- `wait(for:timeout:enforceOrder:)` — Legacy async wait
- `XCTestError.Code` — `timeoutWhileWaiting`, `failureWhileWaiting`

**UI Interruption Monitoring:**
- `addUIInterruptionMonitor(withDescription:handler:)` — Register interruption handler
- `removeUIInterruptionMonitor(_:)` — Remove handler

**Recording and Issues:**
- `record(_: XCTIssue)` — Record a custom issue/failure
- `recordFailure(withDescription:inFile:atLine:expected:)` — Legacy failure recording

**Test Assertions:**
- `XCTAssertTrue` / `XCTAssertFalse`
- `XCTAssertNil` / `XCTAssertNotNil` / `XCTUnwrap`
- `XCTAssertEqual` / `XCTAssertNotEqual` / `XCTAssertIdentical`
- `XCTAssertGreaterThan` / `XCTAssertLessThan`
- `XCTAssertThrowsError`
- `XCTFail(String)`
- `XCTExpectedFailure` — Mark a test as expected to fail

**XCTAttachment (for test results):**
- `XCTAttachment(screenshot:)` — Attach a screenshot
- `XCTAttachment(screenshot:quality:)` — Attach with quality level
- `lifetime: .keepAlways` / `.deleteOnSuccess` — Attachment retention

### xcuiautomation-index (API Index)

**Full XCUIAutomation API Index — extracted from Apple DocC JSON.**

**XCUIElementTypeQueryProvider (element shortcuts):**
Access via any `XCUIElement` or `XCUIElementQuery`:
- `.buttons`, `.textFields`, `.secureTextFields`
- `.tables`, `.cells`, `.collectionViews`
- `.navigationBars`, `.tabBars`, `.toolbars`
- `.switches`, `.sliders`, `.pickers`, `.datePickers`
- `.images`, `.staticTexts`, `.links`
- `.scrollViews`, `.webViews`, `.maps`
- `.activityIndicators`, `.progressIndicators`
- `.searchFields`, `.segmentedControls`
- `.keyboard`, `.keyboards`
- `.alerts`, `.dialogs`, `.sheets`, `.popovers`
- `.menuBars`, `.menuItems`, `.menuButtons`
- `.statusBars`, `.windows`
- `.otherElements` — Catch-all for unclassified elements
- `.firstMatch` — Returns first matching element without throwing

**Keyboard Keys (XCUIKeyboardKey):**
Modifier keys: `.command`, `.control`, `.option`, `.shift`, `.rightCommand`, `.rightControl`, `.rightOption`, `.rightShift`
Navigation: `.upArrow`, `.downArrow`, `.leftArrow`, `.rightArrow`, `.home`, `.end`, `.pageUp`, `.pageDown`
Function keys: `.F1` through `.F19`
Delete: `.delete` (keyIdentifier: "delete")

**XCUIElement.ElementType values:**
`.button`, `.cell`, `.staticText`, `.textField`, `.textField`, `.navigationBar`, `.tabBar`, `.toolbar`, `.switch`, `.slider`, `.pickerWheel`, `.activityIndicator`, `.image`, `.scrollView`, `.table`, `.collectionView`, `.webView`, `.map`, `.alert`, `.dialog`, `.sheet`, `.popover`, `.menuItem`, `.menuBarItem`, `.statusBar`, `.window`, `.keyboard`, `.key`, `.other`, `.group`, `.valueIndicator`, `.levelIndicator`, `.searchField`, `.segmentedControl`, `.picker`, `.datePicker`, `.link`, `.disclosureTriangle`, `.radioButton`, `.checkBox`, `.comboBox`, `.incrementArrow`, `.decrementArrow`, `.toggle`

**XCUIScreen:**
- `XCUIScreen.main` — Main screen singleton
- `.screenshot()` — Capture screenshot of the screen
- `.scale` — Screen scale factor

### patterns (Advanced Patterns)

<!-- Full content from upstream patterns.md follows -->

## Base Test Class Pattern

A reusable base class that handles common setup, teardown, and helpers:

```swift
@MainActor
class BaseUITest: XCTestCase {
    var app: XCUIApplication!

    nonisolated var apiURL: String {
        ProcessInfo.processInfo.environment["API_URL"] ?? "https://api.example.com"
    }

    override func setUp() {
        super.setUp()
        continueAfterFailure = false
        app = XCUIApplication()
        app.terminate()
        app.launchArguments += ["-UITest", "-API_URL", apiURL]
        app.launch()
    }

    override func tearDown() {
        captureScreenshotOnFailure()
        app = nil
        super.tearDown()
    }

    func captureScreenshotOnFailure() {
        guard let failureCount = testRun?.failureCount, failureCount > 0 else { return }
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = "Failure-\(name)"
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    func waitForElement(_ identifier: String, timeout: TimeInterval = 10) -> XCUIElement {
        let element = app.descendants(matching: .any).matching(identifier: identifier).firstMatch
        XCTAssertTrue(element.waitForExistence(timeout: timeout))
        return element
    }

    func takeScreenshot(_ name: String) {
        let attachment = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
```

## Handling iOS System Dialogs

### HealthKit Authorization (iOS 26+)
```swift
func handleHealthKitDialog() {
    let healthAccessText = app.staticTexts["Health Access"]
    if healthAccessText.waitForExistence(timeout: 5) {
        // Scroll to reveal buttons
        let from = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.8))
        let to = app.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.3))
        from.press(forDuration: 0.1, thenDragTo: to)
        if app.buttons["Don't Allow"].waitForExistence(timeout: 5) {
            app.buttons["Don't Allow"].tap()
        }
    }
}
```

### Location Permission
```swift
func handleLocationPermission(allow: Bool) {
    addUIInterruptionMonitor(withDescription: "Location") { alert -> Bool in
        let button = allow ? "Allow While Using App" : "Don't Allow"
        if alert.buttons[button].waitForExistence(timeout: 2) {
            alert.buttons[button].tap()
            return true
        }
        return false
    }
}
```

## Waiting Patterns

### Wait for Element with Predicate
```swift
func waitForNonExistence(_ element: XCUIElement, timeout: TimeInterval) -> Bool {
    let predicate = NSPredicate(format: "exists == false")
    let expectation = XCTNSPredicateExpectation(predicate: predicate, object: element)
    return XCTWaiter().wait(for: [expectation], timeout: timeout) == .completed
}

func waitForValue<T>(_ element: XCUIElement, keyPath: String, timeout: TimeInterval) -> Bool {
    let predicate = NCTKVOExpectation(keyPath: keyPath, object: element)
    return XCTWaiter().wait(for: [predicate], timeout: timeout) == .completed
}
```

### Wait with Retry
```swift
func waitAndRetry<T>(maxAttempts: Int = 3, delay: TimeInterval = 1, action: () throws -> T) rethrows -> T {
    var lastError: Error?
    for attempt in 1...maxAttempts {
        do { return try action() }
        catch { lastError = error; if attempt < maxAttempts { Thread.sleep(forTimeInterval: delay) } }
    }
    throw lastError!
}
```

## Element Query Patterns

### Find by Partial Text
```swift
// Case-insensitive contains
let errorText = app.staticTexts.matching(
    NSPredicate(format: "label CONTAINS[c] 'error'")
).firstMatch

// Regex match
let versionText = app.staticTexts.matching(
    NSPredicate(format: "label MATCHES 'v[0-9]+\\.[0-9]+'")
).firstMatch
```

### Scroll Until Element Visible
```swift
func scrollUntilVisible(_ element: XCUIElement, in scrollView: XCUIElement, maxScrolls: Int = 10) {
    for _ in 0..<maxScrolls {
        if element.isHittable { return }
        scrollView.swipeUp()
        Thread.sleep(forTimeInterval: 0.3)
    }
    XCTAssertTrue(element.isHittable, "Element not visible after \(maxScrolls) scrolls")
}
```

### Check if Table is Empty
```swift
func isTableEmpty(_ tableIdentifier: String) -> Bool {
    return app.tables[tableIdentifier].cells.count == 0
}
```

## Text Field Patterns

### Clear and Type
```swift
extension XCUIElement {
    func clearAndType(_ text: String) {
        tap()
        press(forDuration: 1.0) // Select all
        if XCUIApplication().menuItems["Select All"].waitForExistence(timeout: 2) {
            XCUIApplication().menuItems["Select All"].tap()
        }
        typeText(text)
    }
}
```

### Dismiss Keyboard
```swift
func dismissKeyboard() {
    app.tap()
    if app.buttons["Done"].waitForExistence(timeout: 2) {
        app.buttons["Done"].tap()
    } else if app.buttons["Return"].waitForExistence(timeout: 2) {
        app.buttons["Return"].tap()
    }
}
```

## Debugging

### Print Element Hierarchy
```swift
func printHierarchy() {
    print("=== APP HIERARCHY ===")
    print(app.debugDescription)
}
```

### Diagnostic Test
```swift
func testDiagnostic() {
    print("Buttons: \(app.buttons.count)")
    print("TextFields: \(app.textFields.count)")
    for id in ["tab-home", "submit-button", "main-scroll"] {
        let el = app.descendants(matching: .any).matching(identifier: id).firstMatch
        print("\(id): \(el.exists ? "FOUND" : "NOT FOUND")")
    }
    print(app.debugDescription)
}
```

## Swift 6 @MainActor Requirements

XCUITest classes are `@MainActor`. Mark test classes or individual methods as `@MainActor`:

```swift
@MainActor
class MyUITests: XCTestCase {
    @Test func example() {
        let app = XCUIApplication()
        app.launch()
        // All XCUIElement interactions must be on MainActor
    }
}
```

## Launch Arguments and Environment

Pass test-specific configuration to the app:

```swift
app.launchArguments = [
    "-uitest",
    "-resetState",
    "-debugMode",
]
app.launchEnvironment = [
    "API_BASE_URL": "https://test.example.com",
    "TEST_USER_EMAIL": "test@example.com",
]
app.launch()
```


### Additional XCTest API Reference

**Async Test Expectations (XCTestExpectation):**
- `init(description:)` — Create a named expectation
- `fulfill()` — Mark an expectation as fulfilled
- `expectedFulfillmentCount` — Number of times `fulfill()` must be called
- `assertForOverFulfill` — Fail if `fulfill()` is called more than expected

**XCTWaiter / XCTWaiter.Result:**
- `wait(for:timeout:enforceOrder:)` — Wait for multiple expectations
- `XCTWaiter.Result.completed` — All expectations fulfilled
- `XCTWaiter.Result.timedOut` — Timeout elapsed
- `XCTWaiter.Result.inconclusive` — Interrupted
- `XCTWaiter.Result.failed` — Test failed while waiting

**XCTActivity:**
- `add(_: XCTAttachment)` — Attach a screenshot or data to a test activity
- XCTAttachment supports `lifetime: .keepAlways` (default) or `.deleteOnSuccess`

**Performance Measurement (XCTMetric):**
- `wallClockTime` — Measure elapsed time
- `XCTOSSignpostMetric` — OS signpost-based metrics (for Swift Metrics API)
- `XCTHitchMetric` — Animation hitch time (Core Animation frame drops)
- `XCTMemoryMetric` — Memory usage metrics

**Expected Failures (XCTExpectedFailure):**
- `XCTExpectFailure("issue URL or reason")` — Mark a test as expected to fail
- `Options.isStrict = true` — Test FAILS if it passes (unexpectedly)
- `Options.isStrict = false` — Test passes if it fails (default)

**Skipping Tests:**
- `try XCTSkipIf(condition, "reason")` — Skip if condition is true
- `try XCTSkipUnless(condition, "reason")` — Skip unless condition is true
- `XCTSkip(message:)` — Unconditional skip

