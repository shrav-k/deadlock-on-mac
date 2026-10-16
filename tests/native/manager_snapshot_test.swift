import AppKit
import SwiftUI

// Render only our own views with synthetic fixtures. No desktop capture, Wine,
// account data, real display changes or automation input is involved.
@main struct ManagerSnapshots {
    @MainActor static func main() throws {
        let output = URL(fileURLWithPath: CommandLine.arguments[1])
        let app = NSApplication.shared
        app.setActivationPolicy(.prohibited)
        let model = ManagerModel()
        model.output = #"{"displays":[{"id":"builtin-fixture","name":"Built-in Retina Display","main":true,"builtin":true,"mode_pixels":[3024,1964],"mode_logical":[1512,982],"appkit_backing_scale":2}],"selection":{"phase":"ready","choice":"default","target_id":"builtin-fixture","retina_policy":"auto","retina_enabled":true,"guest":{"bounds":[0,0,3024,1964]},"target_name":"Built-in Retina Display"}}"#
        model.readDisplayReport()
        model.gameModeSetupSummary = "Ready: compatible Apple tool verified and prepared."
        model.playSessionSummary = "Waiting for Deadlock to start through Steam. Check Steam for login, update or Cloud prompts."
        var manifest: [[String: Any]] = []
        for dark in [false, true] {
            for width in [CGFloat(640), CGFloat(820)] {
                for page in ["play-waiting", "play-failed", "settings", "diagnostics"] {
                    model.playSessionSummary = page == "play-failed"
                        ? "Play session failed: Steam reported a stalled main loop before game startup. Previous Game Mode policy restored."
                        : "Waiting for Deadlock to start through Steam. Check Steam for login, update or Cloud prompts."
                    let content = AnyView(VStack(alignment: .leading, spacing: 20) {
                        if page.hasPrefix("play") { PlayView(model: model) }
                        else if page == "settings" { ManagerSettingsView(model: model) }
                        else { ManagerDiagnosticsView(model: model) }
                    }.padding(24).frame(width: width, alignment: .topLeading)
                        .background(Color(nsColor: .windowBackgroundColor))
                        .environment(\.colorScheme, dark ? .dark : .light))
                    let view = NSHostingView(rootView: content)
                    view.appearance = NSAppearance(named: dark ? .darkAqua : .aqua)
                    view.frame.size = view.fittingSize
                    view.layoutSubtreeIfNeeded()
                    precondition(view.bounds.width == width && view.bounds.height > 300)
                    guard let bitmap = view.bitmapImageRepForCachingDisplay(in: view.bounds) else {
                        fatalError("Could not allocate an offscreen fixture image")
                    }
                    view.cacheDisplay(in: view.bounds, to: bitmap)
                    let name = "\(page)-\(dark ? "dark" : "light")-\(Int(width)).png"
                    try bitmap.representation(using: .png, properties: [:])!.write(to: output.appendingPathComponent(name))
                    manifest.append(["file": name, "page": page, "appearance": dark ? "dark" : "light",
                                     "points": [view.bounds.width, view.bounds.height],
                                     "pixels": [bitmap.pixelsWide, bitmap.pixelsHigh]])
                }
            }
        }
        let data: [String: Any] = ["schema": 1, "scope": "Synthetic offscreen manager views; not live UI acceptance",
                                  "os": ProcessInfo.processInfo.operatingSystemVersionString, "images": manifest]
        try JSONSerialization.data(withJSONObject: data, options: [.sortedKeys, .prettyPrinted])
            .write(to: output.appendingPathComponent("manifest.json"))
        print("PASS rendered \(manifest.count) manager fixtures; review images before accepting a visual baseline")
    }
}
