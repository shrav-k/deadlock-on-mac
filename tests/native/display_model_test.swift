import Foundation

@main struct DisplayModelTests {
    @MainActor static func main() {
        let model = ManagerModel()
        model.output = #"{"displays":[{"id":"lg-id","name":"LG ULTRAGEAR","main":false,"builtin":false,"mode_pixels":[2560,1440],"mode_logical":[2560,1440],"appkit_backing_scale":1}],"selection":{"phase":"ready","choice":"lg-id","target_id":"lg-id","retina_policy":"auto","retina_enabled":false,"guest":{"bounds":[1512,-458,2560,1440]},"target_name":"LG ULTRAGEAR"}}"#
        model.readDisplayReport()
        precondition(model.displays.count == 1 && !model.displays[0].main)
        precondition(model.displays[0].label.contains("2560×1440"))
        precondition(model.displayChoice == "lg-id")
        precondition(model.displayPrepareArguments == ["display", "--prepare", "lg-id", "--retina", "auto"])
        precondition(model.displaySummary.contains("Prepared: LG ULTRAGEAR"))
        precondition(model.displaySummary.contains("2560×1440 borderless output · Retina Off"))
        precondition(model.retinaSummary.contains("Automatic: Retina Off"))
        precondition(!model.displayChangesPending)
        model.retinaPolicy = "on"
        precondition(model.retinaSummary.contains("Manual override: Retina On"))
        precondition(model.displayChangesPending)
        model.play()
        precondition(!model.running && model.status.contains("have not been applied"), "Play must not ignore unapplied changes")
        model.retinaPolicy = "auto"
        model.displayChoice = "default"
        precondition(model.displayChangesPending)
        model.output = #"{"displays":[],"selection":{"phase":"ready","choice":"missing-id","retina_policy":"off","target_name":"LG ULTRAGEAR"}}"#
        model.readDisplayReport()
        precondition(model.displayChoice == "missing-id", "Disconnected target must not silently switch")
        precondition(model.retinaPolicy == "off")
        precondition(model.displaySummary.contains("unavailable"))
        precondition(model.selectedDisplay == nil)
        model.output = #"{"displays":[{"id":"builtin","name":"Built-in Retina Display","main":true,"builtin":true,"mode_pixels":[3024,1964],"mode_logical":[1512,982],"appkit_backing_scale":2}],"selection":{"phase":"ready","choice":"default","target_id":"builtin","retina_policy":"auto","retina_enabled":true,"guest":{"bounds":[0,0,3024,1964]},"target_name":"Built-in Retina Display"}}"#
        model.readDisplayReport()
        precondition(model.retinaSummary.contains("Automatic: Retina On"))
        precondition(model.displays[0].geometrySummary.contains("Desktop coordinates: 1512×982"))
        precondition(model.displays[0].geometrySummary.contains("Current backing pixels: 3024×1964"))
        precondition(model.displaySummary.contains("3024×1964 borderless output · Retina On"))
        model.output = model.output.replacingOccurrences(of: #""builtin":true"#, with: #""builtin":false"#)
        model.readDisplayReport()
        precondition(model.retinaSummary.contains("Automatic: Retina On"), "High-DPI external displays also need the automatic Retina policy")
        model.displayChoice = "external"
        precondition(model.selectedDisplay?.id == "builtin")
        model.output = model.output.replacingOccurrences(of: #""target_id":"builtin""#, with: #""target_id":"old-main""#)
        model.readDisplayReport()
        precondition(model.displaySummary.contains("target changed"), "System default must resolve to the prepared screen")
        model.output = #"{"displays":[],"selection":null}"#
        model.readDisplayReport()
        precondition(model.displayChoice == "default" && model.retinaPolicy == "auto")
        model.output = "Malformed helper output"
        model.readDisplayReport()
        precondition(model.displayChoice == "default")
        let oldGameMode = model.automaticGameMode, oldTool = model.gameModeTool
        defer { model.automaticGameMode = oldGameMode; model.gameModeTool = oldTool }
        model.automaticGameMode = true; model.gameModeTool = "/compatible/apple/tool"
        precondition(model.playArguments == ["launch", "--game-mode-tool", "/compatible/apple/tool"])
        precondition(model.setupArguments == ["bootstrap", "--game-mode-tool", "/compatible/apple/tool"])
        let savedSummary = model.displaySummary
        precondition(!model.preparationCompleted(["game-mode", "--prepare"], success: true))
        precondition(model.displaySummary == savedSummary)
        precondition(model.gameModeSetupSummary.contains("Ready:"))
        precondition(!model.preparationCompleted(["game-mode", "--prepare"], success: false))
        precondition(model.gameModeSetupSummary.contains("needs attention"))
        precondition(model.gameModeSummary.contains("restore prior policy"))
        model.automaticGameMode = false
        precondition(model.playArguments == ["launch", "--without-game-mode"])
        precondition(model.gameModeSummary.contains("leave the system policy unchanged"), "Opt-out must not claim the system is Off")
        func session(_ extra: String) -> String {
            let json = "{\"workspace\":\"/Users/example/Deadlock\",\"profile\":\"highball\",\(extra)}"
            return try! JSONDecoder().decode(PlaySessionReport.self, from: Data(json.utf8))
                .summary(workspace: "/Users/example/Deadlock", profile: "highball")
        }
        precondition(session(#""phase":"waiting","restore_pending":true,"watcher_running":true"#).contains("Waiting for Deadlock"))
        precondition(session(#""phase":"playing","restore_pending":true,"watcher_running":true"#).contains("process is running; confirm the game window"))
        precondition(session(#""phase":"finished","restore_pending":false,"error":"Steam stalled""#).contains("Play session failed: Steam stalled"))
        precondition(session(#""phase":"finished","restore_pending":false,"error":"Steam stalled""#).contains("Previous Game Mode policy restored"))
        precondition(session(#""phase":"waiting","restore_pending":true,"watcher_running":false"#).contains("no longer running"))
        precondition(session(#""phase":"restore-failed","restore_pending":true,"restore_error":"service unavailable""#).contains("restoration needs attention"))
        let other = try! JSONDecoder().decode(PlaySessionReport.self, from: Data(#"{"phase":"playing","workspace":"/another","profile":"highball"}"#.utf8))
        precondition(other.summary(workspace: "/Users/example/Deadlock", profile: "highball").contains("No tracked Play session"))
        print("PASS session status: delayed failure, waiting, process-only readiness, restoration failure, interrupted watcher and workspace isolation")
        print("PASS display/Play policy: Retina and standard displays, measured units, saved output, unapplied choices, disconnected/changed targets, Game Mode argv and opt-out")
    }
}
