// Native host metadata for comparison with Wine's virtual coordinates.
// No windows, mode changes, screenshots, serials, or game interaction.
import AppKit
import CoreGraphics
import Foundation

let displays: [[String: Any]] = NSScreen.screens.compactMap { screen in
    guard let number = screen.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? NSNumber,
          let mode = CGDisplayCopyDisplayMode(number.uint32Value),
          let uuid = CGDisplayCreateUUIDFromDisplayID(number.uint32Value)?.takeRetainedValue() else { return nil }
    let id = number.uint32Value
    let bounds = CGDisplayBounds(id)
    return ["name": screen.localizedName,
            "id": CFUUIDCreateString(nil, uuid) as String,
            "mirrored": CGDisplayIsInMirrorSet(id) != 0,
            "session_display_id": id,
            "main": id == CGMainDisplayID(),
            "builtin": CGDisplayIsBuiltin(id) != 0,
            "appkit_backing_scale": screen.backingScaleFactor,
            "quartz_bounds": [bounds.minX, bounds.minY, bounds.width, bounds.height],
            "mode_logical": [mode.width, mode.height],
            "mode_pixels": [mode.pixelWidth, mode.pixelHeight],
            "refresh_hz": mode.refreshRate]
}
let report: [String: Any] = ["inventory_collected": !displays.isEmpty, "displays": displays,
                           "scope": "Host desktop metadata; no game output or visual placement verified"]
let json = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
FileHandle.standardOutput.write(json)
FileHandle.standardOutput.write(Data("\n".utf8))
