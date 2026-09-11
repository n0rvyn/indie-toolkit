# watchOS Sensor & Runtime APIs — 表上能读到什么、能跑多久

Apple Watch 上开发者可用的传感数据面与运行时约束。
可用性**全部用 `swiftc -typecheck` 实测**（判据与负控见 `device-sensor-apis.md` → `AvailabilityByCompiler`），
不从 `API_AVAILABLE` 标注推理——那个推理方式在 2026-09-09 被证明会出错。
版本号来自 **watchOS 26.2 SDK 头文件**的 `watchos(...)` 段。整理于 2026-09-09。

> ⚠️ **本机 Xcode 26.3 只带 watchOS 26.2 SDK。** 标「watchOS 27」的条目一行都没编译过，只有文档背书。
> 判据：`xcodebuild -showsdks | grep -i watch`。

---

<!-- section: WatchSessionBudget keywords: WKExtendedRuntimeSession, 长时会话, 后台, background, 时长上限, HKWorkoutSession, 连续采样 platform: watchOS -->
## ⛔ 先定会话，再挑传感器

**这是 watchOS 与 iOS 最大的结构差异。** iPhone 上「我要持续读传感器」的障碍是没有 motion 后台模式；
表上则相反——有专门的会话机制，但每种都有硬上限，离开会话采集就停。

| 会话 | 运行位置 | 时长上限 | 可预约 |
|---|---|---|---|
| Self care | 前台 | **10 分钟** | 否 |
| Mindfulness | 前台 | **1 小时** | 否 |
| Physical therapy | **后台** | 1 小时 | 否 |
| Smart alarm | **后台** | 30 分钟 | 是（`startAtDate:`，最多提前 36 小时） |
| `HKWorkoutSession` | 随运动 | 运动多久跑多久 | — |

⛔ **头文件里一个时长数字都没有。** grep `mindful|self-care|physical-therapy|smart-alarm|WKBackgroundModes`
across WatchKit headers = 零命中（正控：同样写法命中 `WKExtendedRuntimeSession.h:126` 的 "alarm background mode"）。
上表数字来自 `/documentation/watchkit/using-extended-runtime-sessions`。

官方原文：
- 前台型：「The watch screen doesn't need to remain on to keep your app alive. The session continues until
  the time limit expires, your app invalidates the session, or **the user explicitly leaves your app**
  (for example, by pressing the digital crown or switching to a different app).」
- 后台型：「Background sessions continue to run in the background, **even if the user dismisses the app**.」

`WKExtendedRuntimeSessionInvalidationReason`：`None` / `SessionInProgress` / `Expired` /
**`ResignedFrontmost`**（用户按了表冠——前台型必须为这件事设计）/ `SuppressedBySystem` / `Error`。
错误码里另有 `ScheduledTooFarInAdvance = 2`（>36 小时）、`ExceededResourceLimits = 5`、
`NotApprovedToStartSession = 7`（缺 plist key 或 entitlement）。

⛔ **没有 `BGTaskScheduler`。** `BGTask` / `BGAppRefreshTask` / `BGProcessingTask` /
`BGContinuedProcessingTask` 全部 `API_UNAVAILABLE(watchos)`（编译实测）。
表的周期性后台是 `WKApplicationRefreshBackgroundTask`，且**同时只能排队一个请求，排第二个会取消第一个**。

⛔ **后台超时是崩溃不是静默失败**，`WKBackgroundTask.h:18-20`：
`0xc51bad01` CPU 用太多 · `0xc51bad02` 墙钟用太多 · `0xc51bad03` 系统没给够运行时。

---

<!-- section: WatchBatchedSensor keywords: CMBatchedSensorManager, 800 Hz, 高速采样, 加速度, deviceMotion, workout platform: watchOS -->
## 高速采样：`CMBatchedSensorManager`

`API_AVAILABLE(watchos(10.0))`。每秒投递一批（不是逐样本）。

⛔ **必须有 active `HKWorkoutSession` 才拿得到数据。** WWDC23 session 10179 原文：
「Because this a workout-centric API, you need to have an active HealthKit workout session to get data.」
**头文件里没有这句话**——grep `workout|extended|runtime|session` across `CMBatchedSensorManager.h` 零命中。

| 事实 | 来源 |
|---|---|
| 800 Hz 加速度 / 200 Hz device motion（对比 `CMMotionManager` 上限 100 Hz） | **仅 WWDC23 口头表述**。头文件与文档页都不含任何数字 |
| 「available on Apple Watch Series 8 and Ultra」 | 同上。⚠️ Apple 说的**不是**「and later」，不要替它外推 |
| 真正的运行时判据 | `isAccelerometerSupported` / `isDeviceMotionSupported`（class 属性）；速率读 `accelerometerDataFrequency` / `deviceMotionDataFrequency`（运行时 `NSInteger`，单位 hertz） |

⚠️ **类本身不是 watchOS 独占**：`init` / `startAccelerometerUpdates()` / `accelerometerBatch` /
`isAccelerometerSupported` 在 **iOS SDK 上同样 typecheck 通过**。
只有 Swift async sequence `accelerometerUpdates()` / `deviceMotionUpdates()` 带 `@available(iOS, unavailable)`。
（iPhone 上这些属性运行时是否为 true 未实测——`isAccelerometerSupported` 是唯一判据。）

对比：`CMSensorRecorder.recordAccelerometer(forDuration:)` 是 **50 Hz**（全 CoreMotion 唯一硬编码进头文件的
速率），最长录 12 小时，一次回取最多 12 小时，数据保留 3 天，延迟最多 3 分钟。不需要 workout session。

---

<!-- section: WatchSubmersion keywords: CMWaterSubmersionManager, 深度, depth, 水温, 潜水, Shallow Depth and Pressure, entitlement platform: watchOS -->
## 水下深度与水温：两档门槛

`API_AVAILABLE(watchos(9.0), ios(16.0))`。设 delegate 即触发 TCC 并开始更新，设 nil 即停止。

| 档 | 门槛 | 官方原文 |
|---|---|---|
| **6 米** | Xcode 勾 **Shallow Depth and Pressure** capability，**不用申请** | 「To access data for dives with a maximum depth of 6 meters, add the Shallow Depth and Pressure capability to your app.」 |
| **40 米** | **需向 Apple 申请** 完整 entitlement | 「To enable a maximum depth of 40 meters, you need to apply for the full Submersion Depth and Pressure entitlement.」 |

还要：`NSMotionUsageDescription` + `WKBackgroundModes` = **`underwater-depth`**
（「To make sure your app continues to run, and remains visible」）。

⚠️ **机型：Apple 自己两处打架，以运行时为准。**
- `coremotion/accessing-submersion-data`：「On Apple Watch Ultra, the system sets `waterSubmersionAvailable`
  to true. **On all other devices** and in Simulator, the system sets it to false.」← 旧文
- `updates/coremotion` **September 2024** 段：「**Apple Watch Series 10 supports the Shallow Depth and
  Pressure capability.** Use `CMWaterSubmersionManager` to start a shallow dive session.」
- 用户指南：Series 10 / 11 = 6 m，Ultra 系列 = 40 m
⇒ 判据只认运行时 `waterSubmersionAvailable` 与 `maximumDepth`。

数据形状：`CMWaterSubmersionMeasurement`（`depth` / `pressure` / `surfacePressure` / 六档 `DepthState`）
与 `CMWaterTemperature`（`temperature` + **`temperatureUncertainty`**）。
⛔ **头文件不写单位字面量**，单位由 `NSMeasurement` 的 dimension 在运行时带，别写死米 / kPa / °C。
未下水时 `depth` / `pressure` 为 **nil**；超过授权阈值进 `PastMaxDepth`，再高 10% 进 `SensorDepthError`。

配套触觉：`WKHapticType.underwaterDepthPrompt` / `.underwaterDepthCriticalPrompt`
（头文件注释：「can only be used while the app has an active underwater depth session running」）。

---

<!-- section: WatchOnlyCoreMotion keywords: CMFallDetectionManager, CMMovementDisorderManager, 摔倒, 震颤, 帕金森, entitlement platform: watchOS -->
## watchOS 独占的两个 CoreMotion manager

| 类 | 可用性 | 要点 |
|---|---|---|
| `CMFallDetectionManager` | `API_AVAILABLE(watchos(7.2)) API_UNAVAILABLE(macos, ios, tvos)` | 事件带用户处置四档：`Confirmed` / `Dismissed` / `Rejected` / **`Unresponsive`**。头文件原文要 Apple 批的 entitlement |
| `CMMovementDisorderManager` | `API_AVAILABLE(watchos(5.0)) API_UNAVAILABLE(ios, macos, tvos)` | 震颤六档占比 + 异动症二档，**各自相加恒为 1.0**。`monitorKinesias(forDuration:)` 最长 7 天，结果保留 7 天。头文件限定条件：戴在**症状最重的那只手臂** |

⛔ **两者的 entitlement 标识符字符串在 SDK 里都查不到**——grep 整个框架目录 `com.apple.developer`
只有英文散文（「requires an entitlement from Apple」），没有任何标识符。SafetyKit 的
`SACrashDetectionManager` / `SAEmergencyResponseManager`（`watchos(10.1)`）同样如此。

---

<!-- section: WatchHealthKitGates keywords: HealthKit, HKAuthorizationStatus, 读权限, 授权, NSHealthShareUsageDescription, 传感器量纲 platform: watchOS -->
## HealthKit：读权限查不出来

⛔ **`HKAuthorizationStatus` 只有三个 case，全部以「save」定义，枚举块里 `read` 出现 0 次。**
`requestAuthorization` 的文档原文（同一句在头文件里出现三次）：
「The success parameter … **does NOT indicate whether the application was granted authorization.**」

⇒ **读到空样本时，无法区分「用户没给读权限」与「真的没有数据」。** 每个功能的空态都必须同时兼容两种解释。
能问的只有 `getRequestStatusForAuthorizationToShareTypes:readTypes:` —— 它回答「会不会弹窗」，不回答「给没给」。

权限 key 只有两个：`NSHealthShareUsageDescription`（读）/ `NSHealthUpdateUsageDescription`（写）。
后台投递 `enableBackgroundDeliveryForType:` = `watchos(8.0)`。

传感器衍生量的单位（头文件行尾注释，容易记错的挑出来）：

| 量 | 单位 | 注意 |
|---|---|---|
| `heartRate` | **`count/s`** | ⚠️ 不是 count/min。而 `restingHeartRate` / `walkingHeartRateAverage` / `heartRateRecoveryOneMinute` 是 count/min |
| `heartRateVariabilitySDNN` | ms | |
| `oxygenSaturation` / `atrialFibrillationBurden` / `walkingSteadiness` | % | |
| `appleSleepingWristTemperature` / `waterTemperature` | degC | |
| `environmentalAudioExposure` / `headphoneAudioExposure` | dBASPL | 口径是**等效连续声级**，不是瞬时峰值 |
| `runningPower` / `cyclingPower` | W | |
| `runningGroundContactTime` | ms；`runningVerticalOscillation` cm | |
| `physicalEffort` | kcal/(kg*hr) | |
| `underwaterDepth` | m | |
| `UVExposure` | **头文件的单位注释是空的** | |

睡眠分期对应 AASM（头文件明写）：`AsleepCore` = Stage 1&2 · `AsleepDeep` = Stage 3 · `AsleepREM` = REM。

`HKWorkoutActivityType` 共 84 个枚举值（3 个已废弃）；`SwimBikeRun = 82`（**跳过了 81**）。

**运动镜像到 iPhone**：`startMirroringToCompanionDeviceWithCompletion:`（`watchos(10.0)`，
`API_UNAVAILABLE(ios)`，只能表发起）会在后台拉起手机 App 并给一次性的后台 Live Activity 许可。
⛔ **任意 10 秒窗口最多 100 KB**——高速传感器数据必须在表上先降维。

---

<!-- section: WatchInputOutput keywords: 数字表冠, Digital Crown, WKCrownSequencer, WKHapticType, 双击, handGestureShortcut, wristLocation, 常亮屏, isLuminanceReduced platform: watchOS -->
## 表独有的输入输出面

| 拿什么 | API | 版本 | 权限 |
|---|---|---|---|
| 表冠转速 + 带符号增量 | `WKCrownSequencer.rotationsPerSecond` · `crownDidRotate:rotationalDelta:` | watchOS 3 | 无 |
| 表冠（SwiftUI，带 detent / onChange / onIdle） | `digitalCrownRotation(...)` · `DigitalCrownEvent{offset, velocity}` · `digitalCrownAccessory` | watchOS 6 / 9 | 无 |
| 戴在哪只手 / 表冠朝哪边 | `WKInterfaceDevice.wristLocation` / `.crownOrientation`，变更回调 `deviceOrientationDidChange` | watchOS 3 | 无 |
| 防水等级 / 水锁 | `.waterResistanceRating`（IPX7 / WR50 / WR100）· `.enableWaterLock()` | watchOS 3 / 6.1 | 无 |
| 触觉输出 | `WKInterfaceDevice.play(_:)`，`WKHapticType` **14 种** | watchOS 2 / 7 / 9 | 无 |
| 常亮屏是否已压暗 | `EnvironmentValues.isLuminanceReduced`（**在 SwiftUICore**） | watchOS 8 | 无 |
| 双击手势 | `View.handGestureShortcut(.primaryAction)` | watchOS 11 | 无 |
| 助听器串流在哪只耳 | `AXMFiHearingDevice.streamingEar()` + 变更通知 | watchOS 8 | 无 |

⚠️ **`WKHapticType` 里有 5 种带会话前置条件**（头文件注释明写）：3 种导航类只在 active navigation session
可用，2 种水下深度类只在 depth session 可用。**无会话时静默不响，不报错。**

⛔ **双击只有「指派动作」这一层**：`HandGestureShortcut` 全类型只有 `primaryAction` 一个成员，
没有原始事件流、没有 delegate、没有增量。另有 `ScrollInputKind.handGestureShortcut`（仅 watchOS）。

⛔ **水锁的前提**（头文件原文）：「Only an application which is in an active workout or location session
and is foreground is allowed to enable water lock」。

⚠️ **常亮屏信号不在 WatchKit**——grep WatchKit headers `alwaysOn|uminanceReduc` 零命中，
唯一出口是 SwiftUICore 那个环境值，且它不是 watchOS 独有（iOS 16 / macOS 13 / tvOS 16 也有）。

---

<!-- section: WatchAbsentFrameworks keywords: 没有相机, Vision, Speech, CoreNFC, SensorKit, CBPeripheralManager, CLMonitor, 缺席 platform: watchOS -->
## ⛔ 表上没有的（编译或 `ls` 实测）

**框架目录根本不存在**：`ARKit` · `RoomPlan` · `DockKit` · `CoreNFC` · `ProximityReader` · `SensorKit` ·
`Vision`（watchOS 27 才首次上表）· `PencilKit` · `GameController` · `PHASE` · `Speech` · `MetricKit`

**框架在但类型 `@available(watchOS, unavailable)`**（编译实测）：
`Translation.LanguageAvailability` · `EnergyKit` 全家 · `FinanceKit.FinanceStore` ·
`DeviceActivityCenter` / `FamilyControls` / `ManagedSettings` · `MatterSupport.MatterAddDeviceRequest` ·
`WirelessInsights.ServicePredictionProvider` · `BGTaskScheduler` 全家

**部分角色被排除**：
- `AVCaptureDevice` 全类 `API_UNAVAILABLE(watchos)`——**没有相机**，连 `AVCaptureDeviceTypeMicrophone` 都排除
- `CBPeripheralManager` 的**构造器**不可用，可变 service / characteristic / descriptor 同样
  ⇒ **表不能当 BLE 外设 / GATT server**，只能做 central（`bluetooth-central` 后台扫描要指定 service UUID）
- `CLMonitor` 不可用；地理围栏 / 信标测距 / 显著位置变化全部 `API_UNAVAILABLE(watchos)`。
  后台定位走 `CLBackgroundActivitySession`（watchOS 10）

⚠️ **麦克风反而是可用的**：`AVAudioEngine.inputNode`（watchOS 4）+ `installTap` 拿实时
`AVAudioPCMBuffer`；`AVAudioRecorder`（watchOS 4）；`AVAudioApplication.recordPermission`（watchOS 10）。
SoundAnalysis（watchOS 6）与 ShazamKit（watchOS 8，含 `SHCustomCatalog` 离线自建目录）都能吃这条 tap。
⚠️ 但 `NSMicrophoneUsageDescription` / `NSMotionUsageDescription` / `NSBluetoothAlwaysUsageDescription`
三个字符串在整个 watchOS SDK 里 **0 命中**（正控：`NSHealthShareUsageDescription` 命中 4 个文件、
`NSLocationWhenInUseUsageDescription` 命中 1 个，同一条命令同一次运行）。**SDK 里没有 ≠ 运行时不需要。**

---

<!-- section: WatchOS27Delta keywords: watchOS 27, Vision, FoundationModels, HKWorkoutZoneGroup, CMBodyIdentifiable, 新增 platform: watchOS -->
## watchOS 27 增量

**没有新传感器，没有新的 HealthKit 量化类型**（逐符号 `metadata.platforms` 扫描，方法见
`device-sensor-apis.md` → `SDKVersionBoundsWhatYouSee`；⛔ 不要用 `updates/*` 页判断）。
但有三件「表上第一次有」：

| 新增 | 说明 |
|---|---|
| **Vision** | 首次上表。`ImageRequestHandler` / `DetectBarcodesRequest` / `GenerateObjectnessBasedSaliencyImageRequest` 等 93 个符号整体加了 watchOS。Apple 给的用法：智能裁切让主体填满小屏、读存在表上的条码 |
| **FoundationModels** | 其它平台 26.0，**表上 27.0**。配套 `PrivateCloudComputeLanguageModel` |
| **HealthKit 训练区间** | `HKWorkoutZoneGroup` / `HKWorkoutZoneConfiguration`（来源 app / system / user）/ `HKWorkoutZone{index, minimum, maximum}` / `HKLiveWorkoutZoneUpdate`；`preferredWorkoutZoneConfiguration(for:)` 读用户偏好。**只有心率与骑行功率两种** |

其它：`menopausalState` / `bleedingAfterMenopause` 两个 category 类型；
`HKHealthStore.earliestAuthorizedSampleDate(for:)`。

⚠️ **`CMBodyIdentifiable` / `CMRecordedDeviceMotion` / `CMMotionManager.deviceMotionBody`**（以及
CoreLocation 对称的 `CLBodyIdentifiable` / `headingBody` / `CLActivityType.maritime`）都是 27.0 beta，
**abstract 全空，公开索引里没有任何类型 conform 这个协议**。iOS 侧对应的是「把 `UIView` 设成传感器管理器的
body 让数据按界面朝向对齐」（见 `swift-api-changes-ios27.md`），但 watchOS 没有 `UIView`，谁来当 body 查不到。

⛔ **后台能力零新增**：`BGContinuedProcessingTask` 与新的 `submitTaskRequest` 都不含 watchOS；
长时会话没变；WatchKit 的 beta 扫描 0 条（唯一变化是 `WKExtension` / `WKExtensionDelegate` 在最低目标
watchOS 9.2+ 时标记废弃）。

⚠️ Beta 8 release notes 里一条会影响配件类 App 的行为：第三方心率监测器活动期间，
Apple Watch **暂停后台心率测量与心率通知**（不规则节律、高心率、低心率）。

---

<!-- section: WatchModelMatrix keywords: 机型, Series, Ultra, SE, 血氧, ECG, 皮温, 双击, 睡眠呼吸暂停, 高血压 platform: watchOS -->
## 机型矩阵（SDK 查不到，来自 Apple 支持页）

⛔ **整个 watchOS SDK 里只有两处点名硬件**：
`HKElectrocardiogram.h:19`「Apple Watch Series 4 and above has an electrical heart sensor」，
`WKInterfaceDevice.h:98`「Audio Streaming is supported on Apple Watch Series 3 and later」。
**其余一律运行时 `is*Available` / `is*Supported`，禁止按机型表判断。**

下表只用于产品规划与文案，不用于代码分支：

| 能力 | 机型（Apple 支持页） |
|---|---|
| 血氧 | Series 6+ 与全部 Ultra；**SE 全系不支持** |
| ECG | Series 4+ 与全部 Ultra；**SE 全系不支持** |
| 皮温 | Series 8+、全部 Ultra、SE 3 |
| 深度 + 水温 | Series 10 / 11 = 6 m；Ultra 系列 = 40 m |
| UWB 二代（精确查找） | Series 9+ / Ultra 2+（还要求配对 iPhone 15 系列或更新） |
| 双击 | Series 9+、SE 3、Ultra 2+ |
| 撞车检测 | SE 2、Series 8+、全部 Ultra |
| 常亮屏 | Series 5+、SE 3、全部 Ultra |
| 睡眠呼吸暂停 | Series 9+、Ultra 2、SE 3（⚠️ Ultra 3 两处官方说法不一致） |
| 高血压提示 | Series 9+、Ultra 2+；**SE 全系不支持** |

**当前在售（2026-09）**：Series 11 · SE 3 · Ultra 3，三者都是 **S10 芯片**、四核神经引擎、64 GB。
Apple 只公布 A 编号；`Watch7,x` 式内部标识符没有任何 Apple 页面公布。

⚠️ **区域差异很大**（Apple feature availability 页）：血氧 236 个地区、ECG 187、睡眠呼吸暂停 185、
高血压 178。**睡眠呼吸暂停与高血压都不含中国大陆**（同一份列表里血氧与 ECG 含，所以是真缺席）。

⚠️ **美国血氧的数据路径不同**：2024-01-18 之后在美国购买、部件号以 `LW/A` 结尾的机器，
血氧在**配对的 iPhone 上计算**，只在健康 App 的呼吸分区可见，**表侧读不到**。
Apple 自己的措辞是「a recent U.S. Customs ruling」；ITC / Masimo / 上诉那套说法不在任何 Apple 页面上。
