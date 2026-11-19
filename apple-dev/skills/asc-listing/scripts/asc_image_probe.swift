import Foundation
import ImageIO

func fail(_ message: String) -> Never {
    let result: [String: Any] = ["valid": false, "error": message]
    let data = try! JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
    print(String(data: data, encoding: .utf8)!)
    exit(1)
}

guard CommandLine.arguments.count == 2 else { fail("Expected one reviewed image filepath") }
guard let data = try? Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1])),
      let source = CGImageSourceCreateWithData(data as CFData, nil),
      CGImageSourceGetCount(source) == 1,
      CGImageSourceGetStatus(source) == .statusComplete,
      let type = CGImageSourceGetType(source) as String?,
      type == "public.png" || type == "public.jpeg",
      let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [String: Any],
      let image = CGImageSourceCreateImageAtIndex(source, 0,
        [kCGImageSourceShouldCache: true, kCGImageSourceShouldCacheImmediately: true] as CFDictionary),
      CGImageSourceGetStatusAtIndex(source, 0) == .statusComplete
else { fail("Image is incomplete, invalid, animated or not PNG/JPEG") }

let alpha = (properties[kCGImagePropertyHasAlpha as String] as? Bool) ?? false
let result: [String: Any] = ["valid": true, "format": type == "public.png" ? "PNG" : "JPEG",
                            "width": image.width, "height": image.height, "has_alpha": alpha]
let encoded = try! JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
print(String(data: encoded, encoding: .utf8)!)
