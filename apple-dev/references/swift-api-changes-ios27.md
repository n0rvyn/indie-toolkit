# Swift / SwiftUI API Changes — iOS 27

WWDC 2026 增量。由 `apple-swift-context` skill 按 section 定向加载。

来源：Apple 官方 `/documentation/updates/<框架>` 页的 **June 2026** 段，
以及 `/documentation/ios-ipados-release-notes/ios-ipados-27-release-notes`（**标题写的是 Beta 8**，
凡出自 release notes 的条目都处于 beta 阶段）。整理于 2026-09-07。

> ⚠️ **本机 Xcode 26.3 只带 iOS 26.2 SDK，编译不了本文档里的任何 API。** 要用得先装 Xcode 27。
> 判据：`xcodebuild -showsdks | grep -i ios`。

---

<!-- section: iOS27SensorSurfaceUnchanged keywords: iOS 27, 传感器, sensor, 无新增, ARKit, CoreMotion, updates 页, 缺席证据 platform: iOS -->
## 传感器面：iOS 27 基本无新增 —— 但 updates 页不能当缺席证据

⛔ **本节原先的结论（「零新增」）是错的，2026-09-09 更正。**

原推理：ARKit / AVFoundation / CoreLocation / CoreMotion / DockKit / Matter / Vision /
NearbyInteraction / ProximityReader 的官方 updates 页最新条目停在 June 2024 或 June 2025，
没有 2026 段 ⇒ 没有新增。

**这个推理不成立。`/documentation/updates/<框架>` 页 Apple 已经不再维护。** 实证 2026-09-09：

| 页 | 最新条目 | 该框架实际的 27.0 beta 符号 |
|---|---|---|
| `updates/coremotion` | **September 2024** | 3 个：`CMBodyIdentifiable`、`CMRecordedDeviceMotion`、`CMMotionManager.deviceMotionBody` |
| `updates/watchkit` | **HTTP 404**（页面不存在） | 0 个 |

⚠️ **原来那个「正控」证伪不了这件事**：它只证明*抓取方法*有效（别的框架页返回了正文），
没有证明*这些页面还在更新*。零结果的两种解释里，它只排除了「我抓不到」，没排除「Apple 不写了」。

**正确的判据是逐符号的 `metadata.platforms`**：

```
https://developer.apple.com/tutorials/data/index/<框架>        # 列出符号，新符号带 beta: true
https://developer.apple.com/tutorials/data/documentation/<路径>.json   # 单个符号的 introducedAt / beta
```

这个检查器在 CoreMotion / HealthKit / SensorKit / CoreLocation 上分别返回 5 / 48 / 132 / 3 个非零结果，
所以它报的零可信。

**自相矛盾的痕迹**：本文件下一节 `iOS27SensorOrientationBinding` 记录的「把 `UIView` 设成
`CLLocationManager` / `CMMotionManager` 的 body」——那正是 `CMBodyIdentifiable` /
`CLBodyIdentifiable` 这组新符号。上一版一边写着这个特性，一边断言 CoreMotion 零新增。

⇒ 修正后的结论：**iOS 侧传感器面确实没有新硬件量，但不是「零符号新增」**；
做传感器功能大多不需要 Xcode 27，要用 body 绑定则需要。可用能力目录见 `references/device-sensor-apis.md`。
watchOS 侧不同——Vision 与 FoundationModels 是 watchOS 27 才第一次上表，见 `references/watchos-sensor-apis.md`。

---

<!-- section: iOS27SensorOrientationBinding keywords: CLLocationManager, CMMotionManager, UIView, 朝向, orientation, 坐标系 platform: iOS -->
## 传感器数据按界面朝向对齐（UIKit）

官方原文：「Align sensor data from Core Location and Core Motion with your app's UI orientation by
setting a `UIView` as the body of a `CLLocationManager` or `CMMotionManager` instance.」

**iOS 27 唯一一条直接改传感器 API 的改动。** 以前要自己按 `interfaceOrientation` 转换加速度/磁场/朝向的坐标系，
现在把承载界面的 view 挂给 manager 即可。做罗盘、水平仪、AR 叠加时省掉一层容易写错的手工变换。

---

<!-- section: iOS27PencilKitRecognizer keywords: PKStrokeRecognizer, 手写识别, PencilKit, 笔迹, handwriting platform: iOS -->
## PencilKit：端上手写识别

- `PKStrokeRecognizer` —— 识别手写文字、在墨迹内搜索、生成可索引的字符串内容
- `PKStroke` / `PKStrokePath` 现在 `Identifiable`，有稳定 `id`
- `selection` 属性 + `canvasViewSelectionDidChange(_:)` 可编程选中笔画
- `erasePath(_:mask:transform:)` 沿路径擦除；`bezierRepresentation` 把笔画转 `CGPath`，
  `init(bezierPath:creationDate:pointProvider:)` 反向构造

手写笔记类工具的门槛显著下降：识别与搜索不再需要自己接模型。

---

<!-- section: iOS27MetricKitStateReporting keywords: MetricManager, MXMetricManager, StateReporting, 性能, 指标 platform: iOS -->
## MetricKit 重做 + 新框架 StateReporting

- `MetricManager` 通过 async sequence 投递指标与诊断报告，**取代 `MXMetricManager`** 及其 subscriber 协议
- `MetricReport` 符合 `Codable` / `Sendable`；事件型诊断走 `DiagnosticReport`，逐类型用 `MetricResult` 处理
- 新框架 **`StateReporting`** 与 MetricKit 配合，按 App 自定义状态（而不只是时间区间）切分性能数据

⚠️ `StateReporting` **不在 iOS 26.2 SDK 里**（已核对本机 SDK 的 Frameworks 目录），确认是 iOS 27 独有。

---

<!-- section: iOS27HealthKitZones keywords: HKWorkoutZoneGroup, 心率区间, 骑行功率, HealthKit, 权限历史 platform: iOS -->
## HealthKit

- 心率与骑行功率**区间**：`HKWorkoutZoneGroup` 读区间配置与各区间停留时长；
  `preferredWorkoutZoneConfiguration(for:)` 取用户在健康设置里的偏好；`HKWorkoutZoneConfiguration` 自定义；
  实时更新走 `HKLiveWorkoutBuilderDelegate`
- 权限流新增粒度：用户可授予**部分历史**或**全部历史**
- 新样本类型：`HKCategoryTypeIdentifierMenopausalState`、`HKCategoryTypeIdentifierBleedingAfterMenopause`

---

<!-- section: iOS27SwiftUIChanges keywords: SwiftUI, ContentBuilder, reorderable, swipeActions, 手势输入源, toolbar platform: iOS -->
## SwiftUI

- **手势可指定输入源**（直接触摸 / 间接触摸 / Pencil / 指针）：`DragGesture`、`LongPressGesture`、
  `MagnifyGesture`、`RotateGesture`、`RotateGesture3D`、`SpatialEventGesture`、`SpatialTapGesture`、
  `TapGesture`、`WindowDragGesture` 都有对应初始化器
- `reorderable()` / `reorderContainer(for:isEnabled:move:)` —— 列表、栈、网格、自定义布局都能拖动重排
- `swipeActions(edge:allowsFullSwipe:content:onPresentationChanged:)` + `swipeActionsContainer()`——
  滑动操作不再限于 List
- `ContentBuilder` 统一取代 `ToolbarContentBuilder` / `CommandsBuilder` 等类型专用 builder（需 Xcode 27 构建）
- `@State` 在 Xcode 27 构建时改用 `State()` 宏，引用类型只初始化存储一次
- 工具栏：`visibilityPriority(_:)` 控制空间收窄时谁先进溢出菜单；`ToolbarOverflowMenu`；`topBarPinnedTrailing` 放置
- `AsyncImage` 支持本地缓存（`asyncImageURLSession(_:)`、`init(request:scale:)` 系列）
- 文档型 App：`ReadableDocument` / `WritableDocument` 直接读文件 URL，支持大文件
- 弹窗：`alert(_:item:actions:)` / `alert(error:actions:)` 系列，可由可选数据或 error 驱动

---

<!-- section: iOS27UIKitLifecycle keywords: UIKit, scene-based life cycle, 启动失败, Mac Catalyst platform: iOS -->
## UIKit

- ⛔ **硬性迁移**：官方原文「Starting in iOS 27, apps built with the latest SDK **must use the
  scene-based life cycle or they fail to launch.**」用最新 SDK 构建前先完成场景生命周期迁移
- 传感器朝向绑定（见上面单独一节）
- `UICollectionViewCompositionalLayoutSectionProvider` 闭包纳入自动观察追踪
- `UIRefreshControl` / `UIStepper` 在 Mac Catalyst 的 Mac idiom 下完整支持
- 文本：`NSTextTable` / `NSTextBlock` / `NSTextTableBlock` 表示富文本表格；
  `UITextAttachmentViewProviderReusePolicy` 防滚动闪烁

---

<!-- section: iOS27NewEntitlements keywords: entitlement, Core AI, 后台推理, EnergyKit, TrustInsights platform: iOS -->
## 新增的 entitlement 门槛

| 能力 | entitlement | 说明 |
|---|---|---|
| 后台使用神经引擎 | `com.apple.developer.background-tasks.continued-processing.inference` | iOS 27 起系统默认限制后台访问 ANE，与 GPU 同等对待。大模型（>1 GB）加载性能有改进 |
| EnergyKit 数据进家庭 App | `com.apple.developer.energykit.loadevents-experience` | 家庭 App 自动展示活动日志、历史图表、趋势通知 |
| TrustInsights（新框架） | 在 Xcode target 上声明 TrustInsights capability | 需 entitlement 且需联网才返回结果 |

---

<!-- section: iOS27OtherFrameworks keywords: EnergyKit, Speech, SensitiveContentAnalysis, AudioAccessoryKit, GameController platform: iOS -->
## 其余相关框架

- **EnergyKit**：`ElectricVehicleStatusEvent`（为什么没在充、何时开始、何时停）、
  `ElectricVehicleChargingReason`（`ActiveReason` / `IdleReason`）、`ChargingTarget`、
  `ElectricalLoadDevice` 设备识别、`PerformanceMetrics`（续航估计与电池温度）
- **Speech**：`AssetInputSequenceProvider` / `CaptureInputSequenceProvider` 直接从文件或麦克风取音频；
  `AnalyzerInputConverter` 转换 `AVAudioBuffer`
- **SensitiveContentAnalysis**：`SCSensitivityAnalysis.detectedTypes` 细分类别，
  区分 `sexuallyExplicit` 与 `goreOrViolence`
- **AudioAccessoryKit**：第三方音频配件向系统提供耳机信息以支持固定空间音频。
  本版仅供开发者测试，后续限欧盟用户
- **GameController**：支持 PlayStation Access 控制器，自定义输入配置可存到设备
- **NetworkExtension**：`NEURLFilterManager` 新增 URL 解析配置与过滤报告回传（报告功能仅限受监管设备）
