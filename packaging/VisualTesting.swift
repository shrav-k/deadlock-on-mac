import AppKit
import ScreenCaptureKit
import ImageIO
import UniformTypeIdentifiers

// Public macOS APIs only. No injection into Wine, game hooks, or desktop capture.
// This worker is the signed manager executable so permission identity is stable.
enum VisualFailure: Error, LocalizedError {
    case message(String)
    var errorDescription: String? { if case let .message(text) = self { return text }; return nil }
}

enum VisualGeometry {
    static func bounds(_ frame: CGRect) -> [Double] {
        [Double(frame.minX), Double(frame.minY), Double(frame.width), Double(frame.height)]
    }

    static func contentWindow(layer: Int, width: Double, height: Double) -> Bool {
        // Wine raises its focused fullscreen window above the menu bar (26).
        // Narrow helper strips and popup menus are not application content.
        [0, 3, 26].contains(layer) && width >= 100 && height >= 100
    }

    static func point(x: Double, y: Double, pixels: [Double], frame: [Double]) throws -> CGPoint {
        guard pixels.count == 2, frame.count == 4,
              (pixels + frame + [x, y]).allSatisfy({ $0.isFinite }),
              pixels.allSatisfy({ $0 > 0 }), frame[2] > 0, frame[3] > 0,
              x >= 0, y >= 0, x < pixels[0], y < pixels[1] else {
            throw VisualFailure.message("Click must be inside the captured image.")
        }
        return CGPoint(x: frame[0] + x * frame[2] / pixels[0],
                       y: frame[1] + y * frame[3] / pixels[1])
    }
}

enum VisualKeyHold {
    static func duration(key: String?, command: String?, milliseconds: Int) throws -> Int {
        guard (40...1000).contains(milliseconds), milliseconds == 40 ||
                (command == "key" && ["w", "a", "s", "d"].contains(key ?? "")) else {
            throw VisualFailure.message("Only movement keys may be held, for 40–1000 ms.")
        }
        return milliseconds
    }

    static func run(milliseconds: Int, press: () -> Void, release: () -> Void,
                    validate: () throws -> Void, pause: (Int) -> Void) throws {
        try validate()
        press()
        defer { release() }
        var remaining = milliseconds
        while remaining > 0 {
            let step = min(40, remaining)
            pause(step); remaining -= step
            try validate()
        }
    }
}

@MainActor
enum VisualWorker {
    static let allowedNames = ["deadlock.exe", "steam.exe", "steamwebhelper.exe", "wine-displays.exe"]
    static let keys: [String: CGKeyCode] = ["escape": 53, "return": 36, "tab": 48, "space": 49,
        "left": 123, "right": 124, "down": 125, "up": 126,
        "w": 13, "a": 0, "s": 1, "d": 2, "q": 12, "e": 14, "1": 18, "2": 19, "3": 20, "4": 21]

    static func processText(_ path: String, _ args: [String]) throws -> String {
        let process = Process(), output = Pipe()
        process.executableURL = URL(fileURLWithPath: path); process.arguments = args
        process.standardInput = FileHandle.nullDevice
        process.standardOutput = output; process.standardError = FileHandle.nullDevice
        try process.run()
        let data = output.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        guard process.terminationStatus == 0 else { throw VisualFailure.message("Target process exited or cannot be identified.") }
        return String(decoding: data, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
    }

    static func verify(pid: pid_t, identity: String, prefix: String) throws {
        guard pid > 0, prefix.hasPrefix("/") else { throw VisualFailure.message("Invalid target identity.") }
        let actual = try processText("/bin/ps", ["-ww", "-p", String(pid), "-o", "lstart=,comm="])
        guard actual == identity,
              allowedNames.contains(where: { actual.replacingOccurrences(of: "\\", with: "/").lowercased().hasSuffix("/" + $0) }) else {
            throw VisualFailure.message("Target identity changed or is not a supported Wine application.")
        }
        let cwd = try processText("/usr/sbin/lsof", ["-a", "-p", String(pid), "-d", "cwd", "-Fn"])
        let root = URL(fileURLWithPath: prefix).resolvingSymlinksInPath().path
        guard cwd.split(separator: "\n").contains(where: {
            guard $0.hasPrefix("n/") else { return false }
            let path = URL(fileURLWithPath: String($0.dropFirst())).resolvingSymlinksInPath().path
            return path == root || path.hasPrefix(root + "/")
        }) else { throw VisualFailure.message("Window does not belong to the selected Wine profile.") }
    }

    static func info(_ window: SCWindow) -> [String: Any] {
        ["window_id": window.windowID, "pid": window.owningApplication?.processID ?? 0,
         "title": window.title ?? "", "on_screen": window.isOnScreen,
         "bounds": VisualGeometry.bounds(window.frame)]
    }

    static func windows(_ request: [String: Any]) async throws -> [SCWindow] {
        guard CGPreflightScreenCaptureAccess() else {
            throw VisualFailure.message("Allow Deadlock Manager in System Settings → Privacy & Security → Screen & System Audio Recording, then retry. No image was captured.")
        }
        guard let candidates = request["candidates"] as? [String: String], let prefix = request["prefix"] as? String else {
            throw VisualFailure.message("Missing scoped process candidates.")
        }
        // A Wine window may live in another Space. Capture that window directly;
        // never substitute a desktop image. Input separately requires focus.
        let content = try await SCShareableContent.excludingDesktopWindows(true, onScreenWindowsOnly: false)
        let matching = content.windows.filter {
            candidates[String($0.owningApplication?.processID ?? 0)] != nil
                && VisualGeometry.contentWindow(layer: $0.windowLayer, width: Double($0.frame.width), height: Double($0.frame.height))
        }
        // Steam creates/exits non-window renderer workers during navigation.
        // Verify actual content owners, not unrelated transient child processes.
        for pid in Set(matching.compactMap { $0.owningApplication?.processID }) {
            try verify(pid: pid, identity: candidates[String(pid)]!, prefix: prefix)
        }
        return matching
    }

    static func selected(_ request: [String: Any]) async throws -> SCWindow {
        guard let id = request["window_id"] as? UInt32,
              let window = try await windows(request).first(where: { $0.windowID == id }) else {
            throw VisualFailure.message("The selected window is no longer visible. Capture again.")
        }
        return window
    }

    static func capture(_ request: [String: Any]) async throws -> [String: Any] {
        let window = try await selected(request)
        guard let output = request["output"] as? String, output.hasSuffix(".png"),
              !FileManager.default.fileExists(atPath: output) else { throw VisualFailure.message("Use a new PNG path.") }
        let filter = SCContentFilter(desktopIndependentWindow: window)
        let config = SCStreamConfiguration()
        config.width = Int((filter.contentRect.width * CGFloat(filter.pointPixelScale)).rounded())
        config.height = Int((filter.contentRect.height * CGFloat(filter.pointPixelScale)).rounded())
        guard config.width > 0, config.height > 0, config.width <= 8192, config.height <= 8192,
              config.width * config.height <= 40_000_000 else { throw VisualFailure.message("Unsupported capture size.") }
        config.showsCursor = false; config.capturesAudio = false
        config.ignoreShadowsSingleWindow = true
        config.colorSpaceName = CGColorSpace.sRGB
        let image = try await SCScreenshotManager.captureImage(contentFilter: filter, configuration: config)
        // Refuse a moved/reused window instead of creating an unsafe input receipt.
        let after = try await selected(request)
        guard after.frame == window.frame, after.owningApplication?.processID == window.owningApplication?.processID else {
            throw VisualFailure.message("Window moved during capture. Retry.")
        }
        let data = NSMutableData()
        guard let destination = CGImageDestinationCreateWithData(data, UTType.png.identifier as CFString, 1, nil) else {
            throw VisualFailure.message("Could not encode PNG.")
        }
        CGImageDestinationAddImage(destination, image, nil)
        guard CGImageDestinationFinalize(destination) else { throw VisualFailure.message("PNG encoding failed.") }
        try (data as Data).write(to: URL(fileURLWithPath: output), options: .withoutOverwriting)
        try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: output)
        return info(window).merging(["pixels": [image.width, image.height], "output": output,
                                    "backend": "ScreenCaptureKit", "audio": false]) { _, new in new }
    }

    static func checkGrant(_ request: [String: Any]) throws {
        guard let path = request["grant_path"] as? String,
              let grant = try JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: path))) as? [String: Any],
              grant["enabled"] as? Bool == true,
              let until = grant["expires_at"] as? Double, until > Date().timeIntervalSince1970,
              grant["profile"] as? String == request["profile"] as? String else {
            throw VisualFailure.message("Visual input session is disabled or expired.")
        }
    }

    static func raiseCapturedWindow(_ app: AXUIElement, frame: CGRect) {
        AXUIElementSetMessagingTimeout(app, 1)
        var value: CFTypeRef?
        guard AXUIElementCopyAttributeValue(app, kAXWindowsAttribute as CFString, &value) == .success,
              let items = value as? [AXUIElement] else { return }
        let matches = items.filter {
            var position: CFTypeRef?, size: CFTypeRef?
            guard AXUIElementCopyAttributeValue($0, kAXPositionAttribute as CFString, &position) == .success,
                  AXUIElementCopyAttributeValue($0, kAXSizeAttribute as CFString, &size) == .success,
                  let position, let size, CFGetTypeID(position) == AXValueGetTypeID(), CFGetTypeID(size) == AXValueGetTypeID() else { return false }
            var point = CGPoint.zero, dimensions = CGSize.zero
            guard AXValueGetValue(position as! AXValue, .cgPoint, &point),
                  AXValueGetValue(size as! AXValue, .cgSize, &dimensions) else { return false }
            return CGRect(origin: point, size: dimensions) == frame
        }
        if matches.count == 1 { AXUIElementPerformAction(matches[0], kAXRaiseAction as CFString) }
        // Raising is only a request. Input still requires foreground, geometry,
        // frontmost-window and (for clicks) hit-point validation below.
    }

    static func input(_ request: [String: Any]) async throws -> [String: Any] {
        guard AXIsProcessTrusted() else { throw VisualFailure.message("Allow Deadlock Manager in Privacy & Security → Accessibility, then retry. No input was sent.") }
        try checkGrant(request)
        let window = try await selected(request)
        guard let expected = request["bounds"] as? [Double], expected == info(window)["bounds"] as? [Double],
              let pid = window.owningApplication?.processID,
              let application = NSRunningApplication(processIdentifier: pid) else {
            throw VisualFailure.message("Window bounds or process changed. Capture again.")
        }
        let command = request["command"] as? String
        let hold = try VisualKeyHold.duration(key: request["key"] as? String, command: command,
                                             milliseconds: request["hold_ms"] as? Int ?? 40)
        var point: CGPoint?
        var key: CGKeyCode?
        if command == "click" {
            guard let x = request["x"] as? Double, let y = request["y"] as? Double,
                  let pixels = request["pixels"] as? [Double] else { throw VisualFailure.message("Missing image coordinates.") }
            point = try VisualGeometry.point(x: x, y: y, pixels: pixels, frame: expected)
        } else if command == "key", let name = request["key"] as? String, let code = keys[name] { key = code }
        else { throw VisualFailure.message("Unsupported input. Only one click or a named navigation/game key is accepted.") }
        application.activate(options: [])
        let axApp = AXUIElementCreateApplication(pid)
        AXUIElementSetAttributeValue(axApp, kAXFrontmostAttribute as CFString, kCFBooleanTrue)
        raiseCapturedWindow(axApp, frame: window.frame)
        try await Task.sleep(for: .milliseconds(250))
        guard NSWorkspace.shared.frontmostApplication?.processIdentifier == pid else {
            throw VisualFailure.message("Could not verify foreground focus on the captured application. No input sent.")
        }
        let current = try await selected(request)
        guard current.frame == window.frame else { throw VisualFailure.message("Window moved after focus. Capture again.") }
        // Within the focused app the captured window must be its frontmost normal window.
        let ordered = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
        let front = ordered.first {
            guard ($0[kCGWindowOwnerPID as String] as? Int32) == pid,
                  let layer = $0[kCGWindowLayer as String] as? Int,
                  let bounds = $0[kCGWindowBounds as String] as? [String: Double],
                  let width = bounds["Width"], let height = bounds["Height"] else { return false }
            return VisualGeometry.contentWindow(layer: layer, width: width, height: height)
        }
        guard (front?[kCGWindowNumber as String] as? UInt32) == window.windowID else {
            throw VisualFailure.message("A different window/dialog is in front. Capture it before input.")
        }
        try checkGrant(request)
        let source = CGEventSource(stateID: .privateState)
        let down: CGEvent?, up: CGEvent?
        if let point {
            // PostToPid delivers keys to Wine, but its synthesized mouse events
            // did not acquire a Cocoa window and only changed hover in live tests.
            // Route a click through the system only after verifying the actual
            // topmost window at the point, in addition to PID/focus/geometry.
            let hit = ordered.first {
                guard let raw = $0[kCGWindowBounds as String] as? [String: Any],
                      let frame = CGRect(dictionaryRepresentation: raw as CFDictionary),
                      ($0[kCGWindowAlpha as String] as? Double ?? 0) > 0 else { return false }
                return frame.contains(point)
            }
            guard (hit?[kCGWindowNumber as String] as? UInt32) == window.windowID else {
                throw VisualFailure.message("The click point is covered by another window. No click sent.")
            }
            guard CGWarpMouseCursorPosition(point) == .success else { throw VisualFailure.message("Could not position the pointer. No click sent.") }
            let move = CGEvent(mouseEventSource: source, mouseType: .mouseMoved, mouseCursorPosition: point, mouseButton: .left)
            move?.postToPid(pid)
            usleep(40_000)
            down = CGEvent(mouseEventSource: source, mouseType: .leftMouseDown, mouseCursorPosition: point, mouseButton: .left)
            up = CGEvent(mouseEventSource: source, mouseType: .leftMouseUp, mouseCursorPosition: point, mouseButton: .left)
            down?.setIntegerValueField(.mouseEventClickState, value: 1)
            up?.setIntegerValueField(.mouseEventClickState, value: 1)
        } else if let key {
            down = CGEvent(keyboardEventSource: source, virtualKey: key, keyDown: true)
            up = CGEvent(keyboardEventSource: source, virtualKey: key, keyDown: false)
        } else { throw VisualFailure.message("Missing event.") }
        guard let down, let up else { throw VisualFailure.message("Could not create input events.") }
        guard NSWorkspace.shared.frontmostApplication?.processIdentifier == pid else {
            throw VisualFailure.message("Focus changed before dispatch. No input sent.")
        }
        try checkGrant(request)
        // Mouse routing needs WindowServer; keyboard delivery can remain per-PID.
        // Always release promptly even if focus changes after the press.
        if point != nil {
            down.post(tap: .cghidEventTap); usleep(40_000); up.post(tap: .cghidEventTap)
        } else {
            try VisualKeyHold.run(milliseconds: hold, press: { down.postToPid(pid) }, release: { up.postToPid(pid) }, validate: {
                guard NSWorkspace.shared.frontmostApplication?.processIdentifier == pid else {
                    throw VisualFailure.message("Focus changed; held key released. Capture again.")
                }
                try checkGrant(request)
            }, pause: { usleep(useconds_t($0 * 1000)) })
        }
        return ["events_posted": 2, "pid": pid, "window_id": window.windowID,
                "routing": point == nil ? "pid" : "verified_window_system_mouse",
                "verified_effect": false, "note": "Inspect the new capture before another action."]
    }

    static func execute(_ request: [String: Any]) async throws -> [String: Any] {
        switch request["command"] as? String {
        case "status": return ["screen_recording": CGPreflightScreenCaptureAccess(), "accessibility": AXIsProcessTrusted()]
        case "request-screen":
            return ["screen_recording": CGRequestScreenCaptureAccess(), "note": "Handle any macOS prompt, then retry status/capture."]
        case "request-input":
            let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true] as CFDictionary
            return ["accessibility": AXIsProcessTrustedWithOptions(options), "note": "Handle the macOS permission prompt yourself."]
        case "windows": return ["windows": try await windows(request).map(info)]
        case "capture": return try await capture(request)
        case "click", "key": return try await input(request)
        default: throw VisualFailure.message("Unknown visual worker command.")
        }
    }

    static func main() async -> Int32 {
        do {
            let data = FileHandle.standardInput.readDataToEndOfFile()
            guard data.count <= 65_536, let request = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                throw VisualFailure.message("Invalid visual worker request.")
            }
            let reply = try await execute(request)
            let result = try JSONSerialization.data(withJSONObject: reply, options: [.sortedKeys])
            FileHandle.standardOutput.write(result + Data([10])); return 0
        } catch {
            let data = try! JSONSerialization.data(withJSONObject: ["error": error.localizedDescription])
            FileHandle.standardOutput.write(data + Data([10])); return 1
        }
    }
}
