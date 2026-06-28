import CoreGraphics
import Foundation
// winlist.swift <AppOwnerName?> — print "<id> layer=<n> <W>x<H> <owner>" per on-screen window.
// Filter to one app by passing its owner name; omit to list all.
let owner = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : ""
let opt: CGWindowListOption = [.optionOnScreenOnly]
guard let ws = CGWindowListCopyWindowInfo(opt, kCGNullWindowID) as? [[String: Any]] else { exit(1) }
for w in ws {
    let name = w[kCGWindowOwnerName as String] as? String ?? ""
    if !owner.isEmpty && name != owner { continue }
    let n = w[kCGWindowNumber as String] as? Int ?? -1
    let layer = w[kCGWindowLayer as String] as? Int ?? -1
    let b = w[kCGWindowBounds as String] as? [String: CGFloat] ?? [:]
    print("\(n) layer=\(layer) \(Int(b["Width"] ?? 0))x\(Int(b["Height"] ?? 0)) \(name)")
}
