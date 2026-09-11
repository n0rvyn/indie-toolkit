# Device Sensor APIs — 能读到什么、门槛是什么

iPhone 上开发者可用的传感数据面，按「拿到它要付什么代价」组织。
所有版本号与单位来自 **iOS 26.2 SDK 头文件的 `API_AVAILABLE` 标注**，逐条核对（2026-09-07）。
用于回答「这个物理量能不能拿到 / 要什么权限 / 要什么硬件」，不是 API 用法教程。

> ⚠️ **本文件是 iOS 作用域。Apple Watch 走 `references/watchos-sensor-apis.md`**——同名框架在两个平台上
> 的可用性、权限 key、后台规则都不同，不能互推。
> ⛔ **可用性一律用编译器判，不要读 `API_AVAILABLE` 标注推理**（省略 ≠ 排除）：见下方
> `AvailabilityByCompiler` 一节。本文件 2026-09-09 因为这个错误更正过一次。

---

<!-- section: SensorGateLadder keywords: sensor, 传感器, permission, entitlement, usage description, 门槛 platform: iOS -->
## 四级门槛（先定门槛，再挑 API）

| 级别 | 代价 | 例子 |
|---|---|---|
| 开放 | 什么都不要 | `UIDevice.proximityState`、`ProcessInfo.thermalState`、`UIDevice.batteryLevel`、`GameController` 的 `GCMotion` |
| 用途说明 | Info.plist 一个字符串 | CoreMotion 全家、CoreLocation、麦克风、相机 |
| 硬件 | 特定机型才有 | 气压计、TrueDepth、LiDAR、UWB、DockKit 支架 |
| entitlement | 要 Apple 批 | CoreNFC、ProximityReader、SensorKit、Core AI 后台推理 |

**硬件门槛一律运行时查询，禁止按机型表判断**：
`CMAltimeter.isRelativeAltitudeAvailable` / `ARWorldTrackingConfiguration.supportsSceneReconstruction:` /
`RoomCaptureSession.isSupported` / `NIDeviceCapability`。
NearbyInteraction 头文件里**没有** U1 / U2 / UWB chip 字样，芯片型号与 API 的绑定关系在头文件层面证不了。

---

<!-- section: SensorPermissionKeys keywords: NSMotionUsageDescription, NSMicrophoneUsageDescription, usage description, Info.plist, 权限 platform: iOS -->
## Info.plist usage description key 对照

来源：Xcode 自带 `XCTRunner.app/Info.plist`（随 SDK 分发，为跑自动化测试穷举了当前 SDK 认识的全部 key）。
读法 `plutil -p <该 Info.plist>`；用 `NSCameraUsageDescription` 作阳性对照确认方法有效。

| 能力 | key |
|---|---|
| CoreMotion 全家（`CMMotionManager` / `CMAltimeter` / `CMPedometer` / `CMMotionActivityManager` / `CMSensorRecorder` / `CMHeadphoneMotionManager`） | `NSMotionUsageDescription`（**共用一个**） |
| CoreLocation | `NSLocationWhenInUseUsageDescription` / `NSLocationAlwaysAndWhenInUseUsageDescription` |
| 麦克风 | `NSMicrophoneUsageDescription` |
| 相机 | `NSCameraUsageDescription` |
| CoreNFC | `NFCReaderUsageDescription` + entitlement（见下） |
| CoreBluetooth | `NSBluetoothAlwaysUsageDescription` |
| HealthKit | `NSHealthShareUsageDescription` / `NSHealthUpdateUsageDescription` |
| SensorKit | `NSSensorKitUsageDescription` + `NSSensorKitPrivacyPolicyURL` + 逐传感器的 `NSSensorKitUsageDetail` 字典 |

⚠️ **NearbyInteraction 找不到独立 usage key**：框架目录与整个 platform 目录 grep `UsageDescription` 均零命中
（已用 `NSCameraUsageDescription` 阳性对照）。没有证据说它需要，也没有证据说它不需要。

---

<!-- section: AmbientLightNoPublicLux keywords: lux, illuminance, 照度, ambient light, 环境光, ALS, SensorKit platform: iOS -->
## 环境光：内建传感器的 lux 没有公开出口

**结论**：整个 iOS SDK 里，`NSUnitIlluminance` 在头文件中只出现于 `SRAmbientLightSample.h`
（`NSUnit.h` 是单位定义本身）。验法：

```sh
SDK=$(xcrun --sdk iphoneos --show-sdk-path)
command grep -rl "NSUnitIlluminance" "$SDK/System/Library/Frameworks/"
```

- `SensorKit.SRAmbientLightSample.lux` 是真照度，但 entitlement **只发给 Apple 批准的研究项目**，
  申请表须勾选「数据不用于商业目的、不用于开发商业产品」。商业 App 无解。
  完整门槛与申请流程见 `~/.claude/knowledge/platform-constraints/2026-09-07-sensorkit-lux-entitlement-gated-research.md`。
- ⛔ **`ARLightEstimate.ambientIntensity` 不是照度**。Apple 文档原文单位是**流明**，是喂
  `SCNLight.intensity` 的渲染参数，未给到 lux 的换算。套用按真实 lux 定的档位阈值会系统性判错。
- ✅ 可行路径：从相机曝光态按 ISO 2720 反推。`AVCaptureDevice.ISO` + `.exposureDuration` → EV100 → `E = C · 2^EV100`。
  标定常数 C 有物理先验区间，需要一次照度计对照收敛。参考实现见 Lucent 项目 `Sensing/Photometry.swift` 与 `LogNormalCalibration.swift`。
- 外接光传感器可走 `HMCharacteristicTypeCurrentLightLevel`（HomeKit，头文件原文「a float value in lux」，iOS 9+，只需 usage description）
  或 Matter 的 illuminance 簇。⚠️ 它测的是**配件所在位置**的照度，与手机对着目标面的照度是不同的量。

---

<!-- section: BarometerAndAltitude keywords: CMAltimeter, pressure, kPa, 气压, 海拔, altitude, 楼层 platform: iOS -->
## 气压与高度

| 拿什么 | API | 单位 | 版本 |
|---|---|---|---|
| 气压 | `CMAltimeter.startRelativeAltitudeUpdates` → `CMAltitudeData.pressure` | **kPa**（头文件原文「The pressure in kPa.」） | iOS 8 |
| 相对高度 | 同上 → `.relativeAltitude` | m | iOS 8 |
| 绝对海拔 | `startAbsoluteAltitudeUpdates` → `CMAbsoluteAltitudeData` | m（可为负）+ accuracy / precision | iOS 15 |

- 权限走 `NSMotionUsageDescription`；`CMAltimeter.authorizationStatus`（iOS 11）可查。
- 硬件用 `isRelativeAltitudeAvailable` / `isAbsoluteAltitudeAvailable` 查。
- ⛔ **公开 API 拿不到环境温度**。`CMAmbientPressureData` 带 kPa 与摄氏度且标着 `ios(10.0)`，
  但 CoreMotion 公开头文件里**没有任何在 iPhone 上启动它的入口**；`CMRecordedPressureData` 是
  SensorKit `SRSensorAmbientPressure` 返回的类型，走那道 entitlement。
  同类陷阱：`CMOdometer` 只有数据结构，没有 iPhone 侧 manager。

---

<!-- section: MagnetometerRaw keywords: 磁场, magnetometer, CLHeading, microtesla, 指南针, heading platform: iOS -->
## 磁场

两条路，单位都是微特斯拉：

- `CLHeading.x` / `.y` / `.z` —— `CLHeadingComponentValue`，头文件原文「measured in **microteslas**」
  （`CLHeading.h:19`，属性在 87 / 96 / 105 行）。附 `headingAccuracy`（度）。走定位权限。
- `CMMotionManager` 的 magnetometer 系列（iOS 5+），走 motion 权限，另有 `CMDeviceMotion.magneticField` 带校准精度。

朝向：`CLHeading.magneticHeading` / `.trueHeading`，0–359.9°。

---

<!-- section: MotionAndPedometer keywords: CMMotionManager, CMPedometer, 计步, 步频, cadence, 加速度, 陀螺仪 platform: iOS -->
## 运动

| 拿什么 | API | 版本 |
|---|---|---|
| 三轴加速度 / 旋转率 / 融合姿态 | `CMMotionManager` | iOS 4（磁力计 iOS 5） |
| 步数 / 距离 / 楼层 | `CMPedometer` | iOS 8 |
| 配速 pace / 步频 cadence | `CMPedometer` | iOS 9 |
| 运动状态分类（走 / 跑 / 骑 / 车内） | `CMMotionActivityManager` | iOS 7 |
| 后台加速度录制回取 | `CMSensorRecorder` | iOS 9（`isAuthorizedForRecording` 已废弃） |
| 耳机头部姿态 | `CMHeadphoneMotionManager` | iOS 14 |
| 耳机活动识别 | `CMHeadphoneActivityManager` | iOS 18 |
| 手柄的陀螺 / 加速度 | GameController `GCMotion` | iOS 8（**无需任何 usage description**） |
| 手柄电量 | GameController `GCDeviceBattery` | iOS 14 |

<!-- section: WatchOnlySensorAPIs keywords: watchOS only, CMBatchedSensorManager, CMFallDetectionManager, CMWaterSubmersionManager, 可用性, API_AVAILABLE platform: iOS -->
### 住在 CoreMotion 头文件目录里、但归属容易判错的几个

⛔ **上一版这一节整节的推理方式是错的，2026-09-09 用编译器更正。**
错在把「头文件里没有 `ios(` 子句」当成 iPhone 不可用的证据。**omission 不是 exclusion。**
判据见下一节 `AvailabilityByCompiler`。

CoreMotion 的 watchOS 26.2 与 iOS 26.2 **头文件目录 byte-identical**（`diff -rq` exit 0，
同一 diff 对 CoreLocation 能报出差异）。平台差异全在标注里，而标注要用编译器读，不是用眼睛读。

| 类型 | iOS 真实可用性（`swiftc -typecheck` 实测） |
|---|---|
| `CMBatchedSensorManager` **类本身** | ✅ **iOS 可用**。`init` / `startAccelerometerUpdates()` / `accelerometerBatch` / `isAccelerometerSupported` 全部 typecheck 通过 |
| `CMBatchedSensorManager.accelerometerUpdates()` / `.deviceMotionUpdates()` | ❌ **iOS 不可用** —— `'accelerometerUpdates()' is unavailable in iOS`。Swift async-sequence 扩展带 `@available(iOS, unavailable)`，**类不带**。这才是真正的 watchOS 独占面 |
| `CMWaterSubmersionManager` | ✅ iOS typecheck 通过。硬件门槛在运行时——Apple 明文（`coremotion/accessing-submersion-data`）：「On Apple Watch Ultra, the system sets `waterSubmersionAvailable` to true. **On all other devices** and in Simulator, the system sets it to false.」不再是推断 |
| `CMHighFrequencyHeartRateData` | ✅ iOS typecheck 通过，但**两个平台都没有 producer**（见下） |
| `CMFallDetectionManager` | ❌ 真 iOS 不可用（`API_UNAVAILABLE(ios)`，编译实测确认），且头文件写明需 Apple 批准的 entitlement |
| `CMMovementDisorderManager` | ❌ 真 iOS 不可用（编译实测确认）。结果类型 `CMTremorResult` / `CMDyskineticSymptomResult` 可在 iOS 声明，是误导 |

⛔ **`CMHighFrequencyHeartRateData` 是「有类型没入口」的陷阱**：头文件写「Heart rate data collected at 1Hz」，
带四档 confidence，`ios(17.0), watchos(10.0)`——但 **grep 整个框架目录（含 `.swiftinterface`）找不到任何
vend 它的 API**，只命中它自己和 umbrella 头。正控：同一条 grep 对 `CMAccelerometerData` 命中 7 个文件。
同族陷阱还有 `CMOdometerData`（只有数据结构没有 manager）与 `CMRecordedPressureData`。

---

<!-- section: AvailabilityByCompiler keywords: API_AVAILABLE, 可用性, availability, typecheck, swiftc, 平台判断, unavailable -->
## ⛔ 平台可用性用编译器判，不要读标注推理

**`API_AVAILABLE(ios(5.0))` 而没写 `watchos`，不等于 watchOS 不可用。** 省略 ≠ 排除。
真正的排除是显式的 `API_UNAVAILABLE(watchos)`。

实证 2026-09-09（`CMMotionManager` 的磁力计成员，标注只有 `API_AVAILABLE(ios(5.0))`）：

```sh
SDK=$(xcrun --sdk watchos --show-sdk-path)
cat > t.swift <<'EOF'
import CoreMotion
func p(){ let m = CMMotionManager(); _ = m.isMagnetometerAvailable; m.startMagnetometerUpdates() }
EOF
xcrun swiftc -sdk "$SDK" -target arm64_32-apple-watchos11.0 -typecheck t.swift   # exit 0 —— 可用
```

**必须配负控**，否则你不知道这个方法能不能报出不可用：

```sh
# 已知被显式排除的符号，同一条命令
echo 'import CoreMotion
func p(){ _ = CMStepCounter.isStepCountingAvailable() }' > n.swift
xcrun swiftc -sdk "$SDK" -target arm64_32-apple-watchos11.0 -typecheck n.swift
# → error: 'CMStepCounter' is unavailable in watchOS   (exit 1)
```

target triple 对照：iOS `arm64-apple-ios<版本>` · watchOS `arm64_32-apple-watchos<版本>` ·
macOS `arm64-apple-macos<版本>` · tvOS `arm64-apple-tvos<版本>`。

⚠️ **两个必须知道的边界**：
1. **类可用 ≠ 它的每个成员都可用**。可用性可以挂在 extension 上（`CMBatchedSensorManager` 的 async
   sequence 就是这样），也可以逐成员挂。测你**真正要调的那个符号**，不是测 `import`。
   光 `import Translation` 在 watchOS 上 exit 0，而 `LanguageAvailability()` 报 unavailable。
2. **typecheck 通过 ≠ 硬件存在**。编译只回答「这个 API 在这个平台上声明可见」，
   不回答「这台机器上有这个传感器」。后者一律运行时 `is*Available` / `is*Supported`。

---

<!-- section: HeadphoneMotionGating keywords: CMHeadphoneMotionManager, AirPods, 头部追踪, head tracking, NSMotionUsageDescription, 后台, UIBackgroundModes platform: iOS -->
## 耳机头部姿态：三道门与一个崩溃陷阱

**⛔ 崩溃陷阱（官方原文）**：`CMHeadphoneMotionManager` 文档 Overview 写明——

> In iOS and macOS, include the `NSMotionUsageDescription` key in your app's `Info.plist` file.
> **If this key is absent, the system crashes your app when you start device-motion updates.**

不是权限被拒，是**直接崩**。这是这个 API 最容易踩的一脚。

**硬件门槛只能运行时判**。Apple **没有发布过「CMHeadphoneMotionManager 支持机型表」**。
可参考的是空间音频头部追踪的机型列表（[support.apple.com/en-us/109525](https://support.apple.com/en-us/109525) 查型号，
用户指南 `dev00eb7e0a3` 查头部追踪支持）：**AirPods 3 / AirPods 4 / AirPods Pro（全代）/ AirPods Max**。
⚠️ 两者硬件基础相同（耳机内 IMU），但**「支持空间音频头部追踪」推出「这个 API 可用」是推断，不是 Apple 的直接声明**。
唯一权威判据是 `manager.isDeviceMotionAvailable`。

实测锚点（2026-09-07，Apple 官方型号页）：
- `A2032 / A2031` = **AirPods 2**（2019）→ 不在头部追踪列表内
- `A3047 / A3048 / A3049` = **AirPods Pro 2 with MagSafe Charging Case (USB-C)**（2023）→ 在列表内

**⛔ 没有 `deviceMotionUpdateInterval`**。`CMMotionManager` 有，`CMHeadphoneMotionManager` **没有**——
采样率由系统决定，只能从样本时间戳实测。

**⚠️ `CMDeviceMotion.timestamp` 是开机以来的秒数，不是墙钟。** 要和生命周期事件对齐，
必须在第一帧抓一对 `(motion.timestamp, Date())` 当锚点。

<!-- section: NoMotionBackgroundMode keywords: UIBackgroundModes, 后台, background, CoreMotion, 传感器后台 platform: iOS -->
## ⛔ 没有任何「传感器」后台模式

iOS 的 `UIBackgroundModes` 官方完整取值（`/documentation/xcode/configuring-background-execution-modes` 的表，
2026-09-07 全表 14 行）：

`audio` · `location` · `voip` · `external-accessory` · `bluetooth-central` · `bluetooth-peripheral` ·
`screen-capture` · `fetch` · `remote-notification` · `processing` · `workout-processing`(watchOS) ·
`nearby-interaction` · `push-to-talk`

**没有 motion / CoreMotion 项。** ⇒ 「我要持续读传感器」本身**不构成**让 App 在后台存活的理由，
这是平台设计，不是漏勾了哪个开关。

可走的只有借道：App 因**别的**合法理由活着（例如 `audio` 正在播放、`location` 正在更新）时，
传感器回调会不会继续送——官方文档没写。
⛔ `processing`（`BGTaskScheduler`）是离散任务调度，不是连续流，这条路不通。

**2026-09-07 真机实测（iPhone / iOS 27.0 / AirPods Pro 2 A3048 / `CMHeadphoneMotionManager`）**：

| 臂 | 切后台 | 锁屏 | 全程中断合计 | 有效速率 |
|---|---|---|---|---|
| 不播音频 | **0.73 / 1.3 s 后停止投递**，回前台 0.29–0.48 s 恢复 | — | 62.8 s、120.2 s（均 = 后台时长） | 50.1 Hz |
| 播静音音频（`UIBackgroundModes: audio` + `AVAudioEngine` 输出静音） | 后台 47 s **未断** | 锁屏 37.5 s **未断** | 0.6 s（一次抖动） | 49.9 Hz |

**✅ 确认：不播音频时，App 进后台约 1 秒内停止投递。** 两次独立复现，且与保活臂在
**同一进程内**做了单变量对照（只翻保活开关，其余全同）。

**⚠️ 强证据但只跑了 1 次：播静音音频能把流在后台与锁屏下保住。** 单变量对照成立、
机制清楚，但未满足调试规则 2 的三轮判据，**不写「确认」**。

⇒ 产品含义：耳机头部姿态类的常驻功能**可行**，代价是 App 必须一直播放音频
（对用户是可感知的：占用音频路由、显示在正在播放里）。

**实测采样率 ≈50 Hz**（7460 帧 / 有效 149.5 s）。⛔ 统计速率必须扣掉中断段，
否则空洞撑大分母——首版把同一份数据报成 23.6 Hz。

⛔ **写静音渲染回调时的致命坑**：宿主类型若是 `@MainActor`，`AVAudioSourceNode` 的渲染闭包
会**继承隔离**，在实时音频线程上 `EXC_BREAKPOINT` 当场崩且**编译期零警告**。
闭包要加 `@Sendable`。全文见
`~/.claude/knowledge/bug-postmortem/2026-09-07-mainactor-closure-traps-on-audio-render-thread.md`。

📌 实测工程：`~/Code/Projects/Poise`（🧪 探针）。做法要点：App 被挂起时 Timer 也停，
所以「后台还推不推」**不能在后台实时测**——记录每个样本的时间戳，回前台后做间隔分析。
基线臂（不播音频）与保活臂（播静音音频）必须是同一安装包的两次运行。

<!-- section: DepthAndFaceSensing keywords: TrueDepth, LiDAR, sceneDepth, blendShapes, ARFaceAnchor, RoomPlan, 深度 platform: iOS -->
## 深度与人脸

| 拿什么 | API | 硬件 | 版本 |
|---|---|---|---|
| 人脸表情系数 | `ARFaceAnchor.blendShapes` —— **52 个**通道，各 0…1 | TrueDepth | iOS 11（`TongueOut` iOS 12） |
| 前置深度图 | `AVCaptureDepthDataOutput` + `AVCaptureDeviceTypeBuiltInTrueDepthCamera` | TrueDepth | iOS 11.1 |
| 场景深度 | `ARFrame.sceneDepth` / `.smoothedSceneDepth` | LiDAR | iOS 14 |
| 场景重建网格 | `ARWorldTrackingConfiguration.sceneReconstruction` | LiDAR | iOS 13.4 |
| 结构化房间扫描 | RoomPlan `RoomCaptureSession` | 深度相机 | iOS 16 |
| LiDAR 相机设备类型 | `AVCaptureDeviceTypeBuiltInLiDARDepthCamera` | LiDAR | iOS 15.4 |

⚠️ RoomPlan 的 swiftinterface 里**没有 LiDAR 字样**，只有 `isSupported` 与 `deviceNotSupported`。
门槛究竟是不是 LiDAR，头文件证不了。

---

<!-- section: UWBNearbyInteraction keywords: UWB, NearbyInteraction, NISession, 精确定位, distance, direction platform: iOS -->
## UWB 精确定位

- `NISession`（iOS 14）；`NINearbyObject.distance`（float，米）/ `.direction`（`simd_float3` 单位向量）/
  `.horizontalAngle`（弧度，iOS 16）/ `.verticalDirectionEstimate`（iOS 16）
- 能力查询 `NIDeviceCapability`（iOS 16）：`supportsPreciseDistanceMeasurement` / `supportsDirectionMeasurement` /
  `supportsCameraAssistance`；`supportsExtendedDistanceMeasurement`（iOS 17）；`supportsDLTDOAMeasurement`（iOS 26）
- 配件：`NINearbyAccessoryConfiguration`（iOS 15）

---

<!-- section: NFCAndContactless keywords: CoreNFC, NFC, entitlement, ProximityReader, FeliCa, MiFare platform: iOS -->
## NFC 与非接触卡

- `NFCNDEFReaderSession`（iOS 11）/ `NFCTagReaderSession`（iOS 13）
- 标签类型：`NFCTagTypeISO15693` / `FeliCa` / `ISO7816Compatible` / `MiFare`
- **必须的 entitlement**（头文件原文，`NFCNDEFReaderSession.h:89-93`）：
  「This session requires the `com.apple.developer.nfc.readersession.formats` entitlement in your process.
  In addition your application's Info.plist must contain a non-empty usage description string.」
  FeliCa 另需 `com.apple.developer.nfc.readersession.felica.systemcodes` 数组。
- `ProximityReader`（iOS 15.4 起，部分 API 到 18.4）走另一条路，读支付卡与凭证，需商户资格。

---

<!-- section: AudioSensing keywords: SoundAnalysis, ShazamKit, PHASE, 声音分类, 音频指纹, 空间音频 platform: iOS -->
## 声音侧

| 拿什么 | API | 版本 |
|---|---|---|
| 声音分类 | SoundAnalysis `SNClassifySoundRequest`；分类器标识符 `SNClassifierIdentifierVersion1`（iOS 15） | iOS 13 |
| 音频指纹匹配（**支持自建目录**） | ShazamKit `SHSession` | iOS 15 |
| 空间音频引擎 | PHASE `PHASEEngine` | iOS 15 |

⚠️ **SoundAnalysis 能认哪些类别，头文件里没有静态表**。唯一出口是运行时读
`SNClassifySoundRequest.knownClassifications`（iOS 15）。选题前先跑一次把它打出来。

---

<!-- section: SDKVersionBoundsWhatYouSee keywords: SDK 版本, xcodebuild -showsdks, 枚举能力, iOS 27, 看不见 platform: iOS -->
## ⛔ 用本机 SDK 枚举能力之前，先打出 SDK 版本

从头文件枚举「有没有这个 API」时，**本机 SDK 的版本就是你视野的上界**。
比它新的系统里新增的 API 在头文件里结构性不存在，而 grep 只会返回 0——那个 0 是「我看不见」，不是「不存在」。

**硬动作**（下任何「iOS 没有 X」的结论之前）：

```sh
xcodebuild -version && xcodebuild -showsdks | grep -i ios
```

把版本连同结论一起写出来。SDK 版本低于目标系统时，缺口只能去官方文档补：

```
https://developer.apple.com/tutorials/data{文档路径}.json
```

（`developer.apple.com/documentation/...` 是 SPA，直接抓只得空壳。`/documentation/ios-ipados-release-notes`
是逐版本 release notes。）

⛔ **不要拿 `/documentation/updates/<框架>` 当「这个框架没新增」的证据——Apple 已经不维护那些页了。**
实证 2026-09-09：`updates/coremotion` 最新条目停在 **September 2024**，而 CoreMotion 实际有 3 个
27.0 beta 符号；`updates/watchkit` 直接 **404**。把「最新条目是 2024」读成「没新东西」会得到错误答案，
这个错误已经在 `swift-api-changes-ios27.md` 里发生过一次。

**可信的缺席判据是逐符号的可用性元数据**：

```
https://developer.apple.com/tutorials/data/index/<框架>              # 符号索引，新符号带 beta: true
https://developer.apple.com/tutorials/data/documentation/<路径>.json  # metadata.platforms → introducedAt / beta
```

用它报零之前，先确认它在别处返回过非零（正控）。

实证 2026-09-07：Xcode 26.3 只带 iOS 26.2 SDK，而设备跑 iOS 27。整份传感器枚举漏掉全部 iOS 27 增量，
且当时未声明 SDK 版本。完整教训见 `~/.claude/knowledge/workflow/2026-09-07-local-sdk-version-bounds-capability-survey.md`。
