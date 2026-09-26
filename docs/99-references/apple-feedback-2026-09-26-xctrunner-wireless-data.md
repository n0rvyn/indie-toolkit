# Draft: Apple Feedback — UI tests over Wi-Fi fail with "code 74" on China-region iPhones

Status: **draft, not submitted.** Submit via Feedback Assistant (Developer Tools → Xcode → Testing).
Evidence and method: `~/.claude/knowledge/platform-constraints/2026-09-26-iphone-xctest-code-74-wireless-data-shared-runner-uuid.md`.

---

**Title**
XCUITest runners on China-region iPhones are denied Wi-Fi by the per-app "Wireless Data" setting. The UI test then fails with "test runner exited with code 74" whenever the CoreDevice tunnel was established over Wi-Fi.

**Area**
Xcode › Testing (XCTest / XCUITest on device), CoreDevice network pairing.

**Environment**
- Xcode 26.3 (17C529), macOS 15.8 (24H23)
- iPhone 16 Pro (iPhone17,1), iOS 27.2 (24B5089g), RegionInfo CH/A
- Mac and iPhone on the same Wi-Fi network. The device is connected for development over the network (`devicectl`: `transportType: localNetwork`).
- According to the user, the same failure pattern also occurred on this iPhone under iOS 26.

**Summary**
UI tests run with `xcodebuild test` fail before the runner connects:
- Mac: `The test runner exited with code 74 before establishing connection` (sometimes `… while preparing to run tests`)
- Runner: `Connection peer refused channel request for "dtxproxy:XCTestDriverInterface:XCTestManager_IDEInterface"` → `Exiting due to IDE disconnection`

Unit tests, app install, and `devicectl` file copy on the same device all work. An iPad (iPad8,1, CH/A, iOS 26.7) on the same Mac and Wi-Fi runs the same UI tests fine.

**What we observed**
1. On the iPhone, an `NWConnection` opened by the UI-test runner to a public address reports `currentPath = unsatisfied (Denied over Wi-Fi interface)`. The same code in the iPad runner is `satisfied`.
2. Settings on the iPhone lists every `…UITests-Runner` with a "Wireless Data" option (Off / WLAN / WLAN & Cellular Data), and freshly installed runners show **Off**.
   - After `xcodebuild` reinstalled a runner that had been set to "WLAN & Cellular Data", it showed Off again. This was observed once.
   - The iPad has no "Wireless Data" entry for runners.
3. Every `…UITests-Runner` executable has the same Mach-O UUID, because it is a copy of Xcode's `XCTRunner` (`dwarfdump --uuid`: arm64 `D97065CE-B65A-3502-B46A-BD54DC8651EA`, arm64e `96BE5440-87AF-30CD-884F-D8FA2F592E26`).
   - With 13 runners installed, allowing only one of them left it `Denied over Wi-Fi interface`.
   - Allowing all 13 made it `satisfied`.
4. testmanagerd hands the IDE session socket to the runner ("Initiating serialized transport handoff from IDE connection to test host"). After that, the runner's writes on that connection never reach the Mac:
   - Mac `nettop`: `bytes_in` stops, `re-tx` grows.
   - Every other connection in the same CoreDevice tunnel has zero retransmits.
   - About 18 s later the Mac logs "Launch session expired" and the runner exits 74.
5. Whether this happens depends on the interface the CoreDevice tunnel was **established** on. remotepairingd logs `Got tunnel endpoint: …%en0` for Wi-Fi, en13/en15 for USB.
   - A tunnel established while the iPhone is on USB keeps working after the cable is unplugged and traffic migrates to Wi-Fi.
   - A tunnel established over Wi-Fi fails every time.
   - Flipped three times on the same device: 256 (Wi-Fi) fail → 257 (USB) pass → 260 (Wi-Fi) fail.

**Our inference (not directly observed)**
- The Wireless Data restriction is enforced by matching the executable UUID. Because all runners share one UUID, the settings of different runners collide, and any runner left at Off denies Wi-Fi to all of them.
- A tunnel's virtual interface is delegated to the physical interface it was created on. So on a Wi-Fi-born tunnel, the runner's traffic counts as Wi-Fi traffic.

**Steps to reproduce**
1. Use a China-region iPhone. Connect it to the Mac over Wi-Fi only (no cable).
2. Force the CoreDevice tunnel to be recreated while the phone is on Wi-Fi, e.g. `killall -9 CoreDeviceService`.
3. Run any XCUITest with `xcodebuild test -destination 'platform=iOS,id=<UDID>'`.

**Expected**
The UI test runs. A test runner installed by Xcode should not need a user-facing "Wireless Data" grant to talk to the IDE through the developer tunnel. Its setting should also not be reset on every reinstall, or shared across unrelated runner bundles.

**Actual**
The runner exits with code 74 before establishing the connection, on every run.

**Workarounds**
- Plug in USB, let the tunnel be recreated, then unplug. Tests keep working over Wi-Fi until the tunnel is next recreated on Wi-Fi.
- Or: allow Wireless Data for **every** installed `…UITests-Runner`, then run without reinstalling (`UseDestinationArtifacts = true` in the `.xctestrun`).

**Attachments to add when filing**
- sysdiagnose from the iPhone, taken right after a failing run.
- The `.xcresult` of a failing run.
- Screenshots of the "Wireless Data" page for a runner, and of the stale "(null)" entry that remains after uninstalling a runner. That entry stays Off and cannot be edited.
