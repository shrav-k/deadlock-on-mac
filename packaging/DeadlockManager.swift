import SwiftUI
import AppKit

struct ConnectedDisplay: Identifiable, Decodable {
    let id: String
    let name: String
    let main: Bool
    let builtin: Bool
    let mode_pixels: [Int]
    let mode_logical: [Int]
    let appkit_backing_scale: Double
    var label: String { "\(name) · \(mode_pixels.map(String.init).joined(separator: "×")) px\(main ? " · Main" : "")" }
    var geometrySummary: String {
        "Desktop coordinates: \(mode_logical.map(String.init).joined(separator: "×")) · Current backing pixels: \(mode_pixels.map(String.init).joined(separator: "×")) · \(appkit_backing_scale.formatted())× scale"
    }
}

struct DisplaySelection: Decodable {
    let phase: String
    let choice: String?
    let retina_policy: String?
    let target_name: String?
    let target_id: String?
    let retina_enabled: Bool?
    struct Guest: Decodable { let bounds: [Int] }
    let guest: Guest?
}

struct DisplayReport: Decodable {
    let displays: [ConnectedDisplay]
    let selection: DisplaySelection?
}

// A successful launch command only acknowledges dispatch. The detached watcher
// owns startup/exit and can fail after the command has returned successfully.
struct PlaySessionReport: Decodable {
    let phase: String
    let workspace: String?
    let profile: String?
    let restore_pending: Bool?
    let watcher_running: Bool?
    let error: String?
    let restore_error: String?

    func summary(workspace expectedWorkspace: String, profile expectedProfile: String) -> String {
        guard phase != "idle" else { return "No tracked Play session." }
        guard workspace == URL(fileURLWithPath: expectedWorkspace).standardizedFileURL.resolvingSymlinksInPath().path,
              profile == expectedProfile else { return "No tracked Play session for this workspace and profile." }
        if let restore_error { return "Game Mode restoration needs attention: \(restore_error)" }
        if restore_pending == true && watcher_running != true {
            return "Play watcher is no longer running. Check Diagnostics → Play Session Status before recovery."
        }
        if let error { return "Play session failed: \(error)\(restore_pending == false ? " Previous Game Mode policy restored." : "")" }
        switch phase {
        case "waiting": return "Waiting for Deadlock to start through Steam. Check Steam for login, update or Cloud prompts."
        case "playing" where watcher_running == true && restore_pending == true:
            return "Deadlock process is running; confirm the game window. Game Mode is managed until exit."
        case "finished" where restore_pending == false:
            return "Play session ended. Previous Game Mode policy restored."
        default: return "Play session state is unavailable. Check Diagnostics → Play Session Status."
        }
    }
}

enum PlaySessionReader {
    static func read(resources: URL, workspace: String, profile: String) -> String {
        let process = Process(), pipe = Pipe()
        process.executableURL = resources.appendingPathComponent("python/bin/python3")
        process.arguments = ["-I", "-B", "-u", resources.appendingPathComponent("launcher.py").path,
                             "--workspace", workspace, "--profile", profile, "game-mode", "--session"]
        var env = ["PATH": "/usr/bin:/bin:/usr/sbin:/sbin"]
        for key in ["HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "LC_ALL"] {
            env[key] = ProcessInfo.processInfo.environment[key]
        }
        process.environment = env
        process.standardInput = FileHandle.nullDevice
        process.standardOutput = pipe
        process.standardError = FileHandle.nullDevice
        do {
            try process.run()
            // This read-only helper never spawns Wine or mutates Game Mode.
            let timeout = DispatchWorkItem { if process.isRunning { process.terminate() } }
            DispatchQueue.global().asyncAfter(deadline: .now() + 12, execute: timeout)
            defer { timeout.cancel() }
            var data = Data()
            while true {
                let chunk = pipe.fileHandleForReading.availableData
                if chunk.isEmpty { break }
                data.append(chunk)
                if data.count > 65_536 {
                    if process.isRunning { process.terminate() }
                    process.waitUntilExit()
                    return "Play status could not be read. Check Diagnostics → Play Session Status."
                }
            }
            process.waitUntilExit()
            guard process.terminationStatus == 0 else { throw CocoaError(.fileReadUnknown) }
            return try JSONDecoder().decode(PlaySessionReport.self, from: data).summary(workspace: workspace, profile: profile)
        } catch { return "Play status could not be read. Check Diagnostics → Play Session Status." }
    }
}

@MainActor
final class ManagerModel: ObservableObject {
    @Published var workspace = UserDefaults.standard.string(forKey: "workspace") ?? FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Projects/Games/Deadlock").path {
        didSet { UserDefaults.standard.set(workspace, forKey: "workspace") }
    }
    @Published var profile = UserDefaults.standard.string(forKey: "profile") ?? "highball" {
        didSet { UserDefaults.standard.set(profile, forKey: "profile") }
    }
    @Published private var lifecycle = ManagerLifecycle()
    var running: Bool { lifecycle.running }
    @Published var status = "Ready."
    @Published var output = ""
    @Published var playSessionSummary = "Checking Play session…"
    @Published private(set) var operationStartedAt: Date?
    @Published var gameModeTool = UserDefaults.standard.string(forKey: "gameModeTool") ?? ""
    @Published var gameModeSetupSummary = "Checked automatically during setup. You can also check it here before Play."
    var testingGameMode: Bool { lifecycle.testingGameMode }
    var testingDisplay: Bool { lifecycle.testingDisplay }
    private let activationHandoff = WineActivationHandoff()
    @Published var automaticGameMode = UserDefaults.standard.object(forKey: "automaticGameMode") as? Bool ?? true {
        didSet { UserDefaults.standard.set(automaticGameMode, forKey: "automaticGameMode") }
    }
    private var activeProcess: Process?
    private var diagnosticControl: Pipe?
    private var diagnosticStopRequested = false
    @Published var displays: [ConnectedDisplay] = []
    @Published var displayChoice = "default"
    @Published var retinaPolicy = "auto"
    @Published var displaySummary = "Refresh displays to choose where Deadlock opens."
    @Published private(set) var appliedDisplay: DisplaySelection?

    var selectedDisplay: ConnectedDisplay? {
        let matches = displays.filter {
            displayChoice == "default" ? $0.main : displayChoice == "external" ? !$0.builtin : $0.id == displayChoice
        }
        return matches.count == 1 ? matches[0] : nil
    }
    var displayChangesPending: Bool {
        displayChoice != (appliedDisplay?.choice ?? "default") || retinaPolicy != (appliedDisplay?.retina_policy ?? "auto")
    }
    var retinaSummary: String {
        guard let display = selectedDisplay else { return "Choose one connected display to resolve Retina scaling." }
        let enabled = retinaPolicy == "auto" ? display.appkit_backing_scale > 1 : retinaPolicy == "on"
        let origin = retinaPolicy == "auto" ? "Automatic" : "Manual override"
        return "\(origin): Retina \(enabled ? "On" : "Off") for \(display.name). Applies to this Wine bottle, including Steam."
    }
    var gameModeSummary: String {
        automaticGameMode ? "Game Mode: On during Play; restore prior policy on exit" : "Game Mode: leave the system policy unchanged"
    }
    var playArguments: [String] {
        var arguments = ["launch"]
        if !automaticGameMode { arguments += ["--without-game-mode"] }
        else if !gameModeTool.isEmpty { arguments += ["--game-mode-tool", gameModeTool] }
        return arguments
    }
    var setupArguments: [String] { ["bootstrap"] + playArguments.dropFirst() }

    func refreshDisplays() { run(["display"], label: "Reading connected displays…") }

    func monitorPlaySession() async {
        guard let resources = Bundle.main.resourceURL else { return }
        let selectedWorkspace = workspace, selectedProfile = profile
        while !Task.isCancelled {
            if !running {
                let summary = await Task.detached {
                    PlaySessionReader.read(resources: resources, workspace: selectedWorkspace, profile: selectedProfile)
                }.value
                guard !Task.isCancelled, workspace == selectedWorkspace, profile == selectedProfile else { return }
                playSessionSummary = summary
            }
            do { try await Task.sleep(for: .seconds(3)) } catch { return }
        }
    }

    var displayPrepareArguments: [String] { ["display", "--prepare", displayChoice, "--retina", retinaPolicy] }
    func prepareDisplay() {
        run(displayPrepareArguments, label: "Preparing the selected display; keep Steam closed…")
    }

    func readDisplayReport() {
        guard let data = output.data(using: .utf8),
              let report = try? JSONDecoder().decode(DisplayReport.self, from: data) else { return }
        displays = report.displays
        appliedDisplay = report.selection
        displayChoice = report.selection?.choice ?? "default"
        retinaPolicy = report.selection?.retina_policy ?? "auto"
        if let selected = report.selection, selected.phase == "ready" {
            if selectedDisplay == nil || (selected.target_id != nil && selectedDisplay?.id != selected.target_id) {
                displaySummary = "\(selected.target_name ?? "Saved display") is unavailable or the target changed. Choose a connected display in Settings and apply it."
            } else {
                let bounds = selected.guest?.bounds ?? []
                let output = bounds.count == 4 ? bounds.suffix(2).map(String.init).joined(separator: "×") : "unrecorded"
                let retina = selected.retina_enabled.map { $0 ? "On" : "Off" } ?? "unrecorded"
                displaySummary = "Prepared: \(selected.target_name ?? displayChoice) · \(output) borderless output · Retina \(retina). Play validates this before launch."
            }
        } else {
            displaySummary = "Choose a display, close Windows Steam, then Prepare. macOS main display stays unchanged."
        }
    }

    func chooseGameModeTool() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.prompt = "Use Apple tool"
        panel.message = "Choose a compatible gamepolicyctl from Apple's developer tools. Its Apple signature will be checked before use."
        if panel.runModal() == .OK, let url = panel.url {
            gameModeTool = url.path
            UserDefaults.standard.set(url.path, forKey: "gameModeTool")
        }
    }

    func gameMode(_ arguments: [String] = []) {
        let tool = gameModeTool.isEmpty ? [] : ["--tool", gameModeTool]
        run(["game-mode"] + tool + arguments,
            label: arguments.contains("--test") ? "Game Mode test running; keep this app open." : "Checking Game Mode…")
    }

    func preparationCompleted(_ command: [String], success: Bool) -> Bool {
        if command.first == "game-mode" && command.contains("--prepare") {
            gameModeSetupSummary = success ? "Ready: compatible Apple tool verified and prepared. Setup left Game Mode policy unchanged." : "Game Mode setup needs attention. See Details; install compatible Xcode if no tool was found."
            return false
        }
        guard command.first == "display", success else { return false }
        if command.contains("--prepare") {
            displaySummary = "Display prepared. Open Steam, then Play; check the game menu before gameplay."
            return !lifecycle.quitPending
        }
        if command.contains("--clear") {
            displaySummary = "Display management is off; current game and Retina settings were preserved."
        }
        return false
    }

    private func stopDiagnostic() {
        guard lifecycle.cancellableDiagnostic else { return }
        diagnosticStopRequested = true
        status = testingDisplay ? "Closing the test grid…" : "Restoring Game Mode…"
        try? diagnosticControl?.fileHandleForWriting.close()
    }
    func stopGameModeTest() { stopDiagnostic() }
    func stopDisplayTest() { stopDiagnostic() }

    func requestQuit() -> ManagerQuitDecision {
        let decision = lifecycle.requestQuit()
        switch decision {
        case .quitNow: break
        case .waitForOperation:
            status = "Finishing the current operation before quitting the manager…"
        case .stopDiagnosticAndWait:
            status = testingDisplay ? "Closing the test grid before quitting the manager…" : "Restoring Game Mode before quitting the manager…"
            stopDiagnostic()
        }
        return decision
    }

    private func finished(success: Bool) {
        try? diagnosticControl?.fileHandleForWriting.close()
        diagnosticControl = nil
        activeProcess = nil
        operationStartedAt = nil
        let result = lifecycle.finish(success: success)
        // A busy quit was cancelled, not deferred into AppKit's modal termination
        // loop. Resubmit only after the worker has finished successfully so its
        // MainActor output/completion callbacks keep running on the normal loop.
        if result.shouldQuit { NSApp.terminate(nil) }
    }

    func play() {
        guard !displayChangesPending else {
            status = "Display choices have not been applied. Close Windows Steam, then use Settings → Apply Display before Play."
            return
        }
        run(playArguments, label: "Starting Deadlock through Steam…")
    }

    func chooseWorkspace() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true
        panel.prompt = "Use folder"
        if panel.runModal() == .OK, let url = panel.url { workspace = url.path }
    }

    func run(_ command: [String], label: String) {
        guard !running, let resources = Bundle.main.resourceURL, lifecycle.begin(command) else { return }
        status = label
        output = ""
        diagnosticStopRequested = false
        operationStartedAt = Date()
        let selectedWorkspace = workspace
        let selectedProfile = profile
        let diagnostic = lifecycle.cancellableDiagnostic
        activationHandoff.arm(workspace: selectedWorkspace, profile: selectedProfile, command: command) { [weak self] text in
            self?.output += text
        }
        Task.detached {
            let process = Process()
            process.executableURL = resources.appendingPathComponent("python/bin/python3")
            process.arguments = ["-I", "-B", "-u", resources.appendingPathComponent("launcher.py").path,
                                 "--workspace", selectedWorkspace, "--profile", selectedProfile]
                + (diagnostic ? ["--manager-control-stdin"] : []) + command
            var env: [String: String] = ["PATH": "/usr/bin:/bin:/usr/sbin:/sbin"]
            for key in ["HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "LC_ALL"] {
                env[key] = ProcessInfo.processInfo.environment[key]
            }
            process.environment = env
            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = pipe
            let control = diagnostic ? Pipe() : nil
            process.standardInput = control.map { $0 as Any } ?? FileHandle.nullDevice
            do {
                try process.run()
                try? control?.fileHandleForReading.close()
                await MainActor.run {
                    self.activeProcess = process
                    self.diagnosticControl = control
                    if (self.lifecycle.quitPending || self.diagnosticStopRequested) && self.lifecycle.cancellableDiagnostic {
                        try? control?.fileHandleForWriting.close()
                    }
                }
                while true {
                    let data = pipe.fileHandleForReading.availableData
                    if data.isEmpty { break }
                    let text = String(decoding: data, as: UTF8.self)
                    await MainActor.run {
                        self.output += text
                        // Keep a noisy diagnostic from retaining unbounded UI memory.
                        if self.output.count > 200_000 { self.output = String(self.output.suffix(160_000)) }
                    }
                }
                process.waitUntilExit()
                let code = process.terminationStatus
                await MainActor.run {
                    let messages = ["bootstrap": "Steam installed. Open Steam and allow it to update.",
                                    "steam": "Steam is starting. First startup may take a few minutes before sign-in appears.",
                                    "install": "Install request sent. Complete the download in Steam.",
                                    "launch": "Play request sent. Live session status is shown on the Play page.",
                                    "exit": "Deadlock is closed. Steam remains open; check Details for Game Mode restoration.",
                                    "steam-exit": "Windows Steam is closed. Check Details for Game Mode restoration.",
                                    "performance": "Settings saved. Restart Windows Steam for them to apply.",
                                    "graphics-preset": "Display settings saved with a backup. Verify them in the game.",
                                    "game-mode": "Game Mode operation finished. Check the policy in Details."]
                    self.status = code == 0 ? (messages[command.first ?? ""] ?? "Check complete.")
                        : "This step could not finish. See details below (code \(code))."
                    if code == 0 && command == ["display"] { self.readDisplayReport() }
                    let refreshPreparedDisplay = self.preparationCompleted(command, success: code == 0)
                    self.finished(success: code == 0)
                    if refreshPreparedDisplay { self.refreshDisplays() }
                }
            } catch {
                try? control?.fileHandleForReading.close()
                try? control?.fileHandleForWriting.close()
                let message = error.localizedDescription
                await MainActor.run { self.status = message; self.finished(success: false) }
            }
        }
    }
}

enum ManagerPage: String, CaseIterable, Identifiable {
    case play = "Play", settings = "Settings", diagnostics = "Diagnostics"
    var id: String { rawValue }
    var icon: String {
        switch self { case .play: "play.fill"; case .settings: "slider.horizontal.3"; case .diagnostics: "stethoscope" }
    }
}

struct ContentView: View {
    @ObservedObject var model: ManagerModel
    @State private var page: ManagerPage? = .play
    var body: some View {
        NavigationSplitView {
            VStack(spacing: 0) {
                List(ManagerPage.allCases, selection: $page) { item in
                    Label(item.rawValue, systemImage: item.icon).tag(item)
                }.listStyle(.sidebar)
                VStack(alignment: .leading, spacing: 8) {
                    Text("DEVELOPMENT PREVIEW").font(.caption2).foregroundStyle(.secondary)
                    Button("Quit Manager") { NSApp.terminate(nil) }.buttonStyle(.plain)
                }.padding(16).frame(maxWidth: .infinity, alignment: .leading)
            }.navigationSplitViewColumnWidth(min: 150, ideal: 170, max: 210)
        } detail: {
            VStack(spacing: 0) {
                ScrollView {
                    VStack(alignment: .leading, spacing: 20) {
                        switch page ?? .play {
                        case .play: PlayView(model: model)
                        case .settings: ManagerSettingsView(model: model)
                        case .diagnostics: ManagerDiagnosticsView(model: model)
                        }
                    }.padding(24).frame(maxWidth: .infinity, alignment: .leading)
                }
                Divider()
                OperationStatusView(model: model).padding(16)
            }
        }.frame(minWidth: 820, minHeight: 640)
            .task(id: model.workspace + "\n" + model.profile) { await model.monitorPlaySession() }
    }
}

struct PlayView: View {
    @ObservedObject var model: ManagerModel
    var body: some View {
        VStack(alignment: .leading, spacing: 24) {
            Image(systemName: "gamecontroller.fill").font(.system(size: 44)).foregroundStyle(.orange)
            VStack(alignment: .leading, spacing: 8) {
                Text("Deadlock").font(.largeTitle.bold())
                Text("Your Steam account, library and friends.").foregroundStyle(.secondary)
            }
            HStack(spacing: 12) {
                Button { model.play() } label: { Label("Play", systemImage: "play.fill").frame(minWidth: 90) }
                    .buttonStyle(.borderedProminent).tint(.orange)
                Button("Exit Deadlock") { model.run(["exit"], label: "Asking Steam to close Deadlock…") }
                Menu("Steam") {
                    Button("Open Windows Steam") { model.run(["steam"], label: "Opening Steam…") }
                    Button("Exit Windows Steam") { model.run(["steam-exit"], label: "Closing Deadlock and Windows Steam…") }
                }.fixedSize()
            }.controlSize(.large).disabled(model.running)
            Label(model.playSessionSummary, systemImage: "info.circle")
                .font(.callout).textSelection(.enabled).accessibilityIdentifier("play-session-status")
            GroupBox {
                VStack(alignment: .leading, spacing: 14) {
                    Label(model.displaySummary, systemImage: "display")
                    if model.displayChangesPending {
                        Label("Display changes pending. Apply them in Settings before Play.", systemImage: "exclamationmark.circle")
                    }
                    Label(model.gameModeSummary, systemImage: "speedometer")
                    Text("This is your launch policy, not a live status reading. Steam alone leaves Game Mode unchanged. Quitting this manager leaves the game and its watcher running.")
                        .font(.caption).foregroundStyle(.secondary)
                }.frame(maxWidth: .infinity, alignment: .leading).padding(10)
            }
            Text("First time here? Open Settings → Installation to set up Steam, sign in and install Deadlock.")
                .font(.callout).foregroundStyle(.secondary)
        }
    }
}

struct OperationStatusView: View {
    @ObservedObject var model: ManagerModel
    @State private var showOutput = false
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top) {
                if model.running { ProgressView().controlSize(.small) }
                Text(model.status).font(.callout).textSelection(.enabled)
                Spacer()
                if model.testingDisplay { Button("Stop Grid") { model.stopDisplayTest() } }
                if model.testingGameMode { Button("Stop and Restore") { model.stopGameModeTest() } }
                if let started = model.operationStartedAt {
                    TimelineView(.periodic(from: started, by: 1)) { context in
                        Text("\(max(0, Int(context.date.timeIntervalSince(started))))s")
                            .font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                    }
                }
            }
            DisclosureGroup("Operation details", isExpanded: $showOutput) {
                ScrollView {
                    Text(model.output.isEmpty ? "No operation output." : model.output)
                        .font(.system(.caption, design: .monospaced)).textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }.frame(height: 150)
            }.font(.caption)
        }
    }
}

struct ManagerSettingsView: View {
    @ObservedObject var model: ManagerModel
    var body: some View {
        Text("Settings").font(.largeTitle.bold())
        GroupBox("Display") {
            VStack(alignment: .leading, spacing: 12) {
                Picker("Play on", selection: $model.displayChoice) {
                    Text("System main display").tag("default")
                    Text("Prefer external (one connected)").tag("external")
                    ForEach(model.displays) { display in Text(display.label).tag(display.id) }
                    if !["default", "external"].contains(model.displayChoice) && !model.displays.contains(where: { $0.id == model.displayChoice }) {
                        Text("Saved display — disconnected").tag(model.displayChoice)
                    }
                }
                Picker("Retina scaling", selection: $model.retinaPolicy) {
                    Text("Automatic — match selected display").tag("auto")
                    Text("On — manual override").tag("on"); Text("Off — manual override").tag("off")
                }
                Text(model.retinaSummary).font(.callout)
                if let display = model.selectedDisplay {
                    DisclosureGroup("Display measurements") {
                        Text(display.geometrySummary).font(.caption).textSelection(.enabled)
                        Text("Backing pixels describe the current macOS mode. Wine's output and the game's internal render scale are separate measurements.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
                HStack {
                    Button("Refresh") { model.refreshDisplays() }
                    Button("Apply Display") { model.prepareDisplay() }
                }
                Text(model.displaySummary).font(.caption).fixedSize(horizontal: false, vertical: true)
                Text("Close Windows Steam before applying. Saves a backup, sets borderless output and matches Wine scaling to this display. Your macOS main display stays unchanged.")
                    .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }.padding(8)
        }.disabled(model.running)
        GroupBox("Game Mode") {
            VStack(alignment: .leading, spacing: 10) {
                Toggle("Enable during Play and restore on exit", isOn: $model.automaticGameMode)
                Text("Recommended on for both laptop and external displays. No play-time limit; the watcher continues after Command–Tab or closing the manager. Turning this preference off affects the next launch and leaves the system policy unchanged.").font(.caption).foregroundStyle(.secondary)
                Button("Check Game Mode Setup") { model.gameMode(["--prepare"]) }
                Text(model.gameModeSetupSummary).font(.caption)
                Text("Setup automatically finds a compatible Apple tool, verifies it and keeps a local copy. If none is available, install or update Xcode and check again. You do not need to select a file or change your default developer tools.")
                    .font(.caption).foregroundStyle(.secondary)
                Link("Get Xcode from Apple", destination: URL(string: "https://apps.apple.com/app/xcode/id497799835")!)
                DisclosureGroup("Advanced tool override") {
                    HStack {
                        Button("Choose…") { model.chooseGameModeTool() }
                        Button("Use Automatic") { model.gameModeTool = ""; UserDefaults.standard.removeObject(forKey: "gameModeTool") }
                        Text(model.gameModeTool.isEmpty ? "Automatic discovery and compatibility checks" : model.gameModeTool)
                            .font(.caption).lineLimit(2).truncationMode(.middle).textSelection(.enabled)
                    }
                }
            }.padding(8)
        }.disabled(model.running)
        GroupBox("Performance") {
            VStack(alignment: .leading, spacing: 10) {
                Button("Set game and menu limits to 60 FPS") {
                    model.run(["game-fps", "--cap", "60", "--menu-cap", "60", "--apply"], label: "Backing up and saving FPS limits…")
                }
                Text("Requires Windows Steam closed. Resolution, rendering quality and upscaling are separate settings; test them in the game after display qualification.")
                    .font(.caption).foregroundStyle(.secondary)
            }.frame(maxWidth: .infinity, alignment: .leading).padding(8)
        }.disabled(model.running)
        DisclosureGroup("Installation") {
            VStack(alignment: .leading, spacing: 12) {
                HStack { TextField("Workspace", text: $model.workspace); Button("Choose Folder…") { model.chooseWorkspace() } }
                TextField("Runtime profile", text: $model.profile)
                HStack {
                    Button("Set Up Steam") { model.run(model.setupArguments, label: "Checking prerequisites, then installing verified components and Steam…") }
                    Button("Open Steam") { model.run(["steam"], label: "Opening Steam…") }
                    Button("Install Deadlock") { model.run(["install"], label: "Opening Deadlock in Steam…") }
                }
                Text("Sign in and complete Steam Guard in Windows Steam. Steam handles downloads and updates. A new workspace creates a separate installation and uses more disk space.")
                    .font(.caption).foregroundStyle(.secondary)
            }.padding(.top, 8).disabled(model.running)
        }
    }
}

struct ManagerDiagnosticsView: View {
    @ObservedObject var model: ManagerModel
    @State private var presentation = "popup"
    @State private var displayMode = "borderless"
    @State private var displayWidth = ""
    @State private var displayHeight = ""
    var body: some View {
        Text("Diagnostics").font(.largeTitle.bold())
        Text("Display checks run without gameplay. Results and partial logs stay in your workspace.").foregroundStyle(.secondary)
        GroupBox("Display test") {
            VStack(alignment: .leading, spacing: 12) {
                Picker("Window presentation", selection: $presentation) {
                    Text("Win32 borderless popup (baseline)").tag("popup")
                    Text("SDL fullscreen desktop (candidate)").tag("sdl-desktop")
                }
                Button("Start Test Grid") {
                    model.run(["display", "--test-window", "--presentation", presentation],
                              label: "Grid: check four edges, click corner squares, then Command–Tab away and back…")
                }
                Text("Apply the connected display in Settings first, with Steam closed. Check the menu bar with the pointer centered. Escape or Stop Grid closes the test; there is no timer.")
                    .font(.caption).foregroundStyle(.secondary)
            }.padding(8)
        }.disabled(model.running)
        GroupBox("Checks") {
            HStack {
                Button("Check Setup") { model.run(["doctor"], label: "Checking installation…") }
                Button("Game Mode Status") { model.gameMode() }
                Button("Play Session Status") { model.gameMode(["--session"]) }
            }.frame(maxWidth: .infinity, alignment: .leading).padding(8)
        }.disabled(model.running)
        DisclosureGroup("Performance recording") {
            Button("Enable 60 FPS cap and Metal HUD logging") {
                model.run(["performance", "--fps-cap", "60", "--hud", "on", "--hud-log", "on"], label: "Saving performance recording settings…")
            }.padding(.top, 8).disabled(model.running)
        }
        DisclosureGroup("Recovery") {
            VStack(alignment: .leading, spacing: 10) {
                Button("Recover Interrupted Play") { model.gameMode(["--restore-session"]) }
                Button("End Game Mode Session and Restore") { model.gameMode(["--stop-session"]) }
                Button("Restore Interrupted Timed Test") { model.gameMode(["--restore"]) }
                Button("Let the Game Manage Displays") { model.run(["display", "--clear"], label: "Disabling display management…") }
            }.padding(.top, 8).disabled(model.running)
        }
        DisclosureGroup("Experimental display settings") {
            VStack(alignment: .leading, spacing: 10) {
                Text("These direct game settings can invalidate the prepared display. Fullscreen is still under qualification; close Steam and retain the backup.")
                    .font(.caption).foregroundStyle(.secondary)
                Picker("Mode", selection: $displayMode) {
                    Text("Borderless").tag("borderless"); Text("Exclusive fullscreen").tag("fullscreen")
                }
                HStack {
                    TextField("Width", text: $displayWidth).frame(width: 80)
                    Text("×"); TextField("Height", text: $displayHeight).frame(width: 80)
                    Button("Preview") { model.run(["graphics-preset", "--mode", displayMode, "--width", displayWidth, "--height", displayHeight], label: "Previewing display changes…") }
                    Button("Apply with Backup") { model.run(["graphics-preset", "--mode", displayMode, "--width", displayWidth, "--height", displayHeight, "--apply"], label: "Saving display settings…") }
                }
            }.padding(.top, 8).disabled(model.running)
        }
        DisclosureGroup("Wine startup and exit fixes") {
            HStack {
                Button("Check") { model.run(["wine-hotfix"], label: "Verifying Wine fixes…") }
                Menu("Change Version") {
                    Button("Use Current Fixes") { model.run(["wine-hotfix", "--set", "on"], label: "Enabling verified startup and exit fixes…") }
                    Button("Restore Exit-Only Fix") { model.run(["wine-hotfix", "--set", "previous"], label: "Restoring the exit-only revision…") }
                    Button("Disable All Fixes") { model.run(["wine-hotfix", "--set", "off"], label: "Disabling Wine fixes…") }
                }
            }.padding(.top, 8).disabled(model.running)
            Text("Close Windows Steam before changing versions. Explicit rollback and disabled choices are preserved during setup.")
                .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
        }
        DisclosureGroup("Timed Game Mode diagnostic") {
            Button("Test for Five Minutes") { model.gameMode(["--test", "--seconds", "300"]) }
                .padding(.top, 8).disabled(model.running)
        }
    }
}

@MainActor
final class ManagerAppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    // AppKit owns this single utility window. Replacing the delegate of a
    // SwiftUI-owned Window is unreliable: SwiftUI can reclaim it and close the
    // app while a child operation is still running.
    let model = ManagerModel()
    private(set) var window: NSWindow?
    private let presentWindow: Bool

    init(presentWindow: Bool = true) { self.presentWindow = presentWindow }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 940, height: 720),
                              styleMask: [.titled, .closable, .miniaturizable, .resizable],
                              backing: .buffered, defer: false)
        window.title = "Deadlock Manager"
        window.isReleasedWhenClosed = false
        window.contentMinSize = NSSize(width: 820, height: 640)
        window.contentView = NSHostingView(rootView: ContentView(model: model))
        window.delegate = self
        window.center()
        self.window = window
        installMenu()
        if presentWindow {
            window.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
            model.refreshDisplays()
        }
    }

    private func installMenu() {
        let menu = NSMenu()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "About Deadlock Manager", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Hide Deadlock Manager", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quit Deadlock Manager", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let appItem = menu.addItem(withTitle: "Deadlock Manager", action: nil, keyEquivalent: "")
        appItem.submenu = appMenu
        let editMenu = NSMenu(title: "Edit")
        for (title, action, key) in [("Undo", "undo:", "z"), ("Cut", "cut:", "x"),
                                     ("Copy", "copy:", "c"), ("Paste", "paste:", "v"),
                                     ("Select All", "selectAll:", "a")] {
            editMenu.addItem(withTitle: title, action: Selector(action), keyEquivalent: key)
        }
        menu.addItem(withTitle: "Edit", action: nil, keyEquivalent: "").submenu = editMenu
        let windowMenu = NSMenu(title: "Window")
        windowMenu.addItem(withTitle: "Minimize", action: #selector(NSWindow.performMiniaturize(_:)), keyEquivalent: "m")
        windowMenu.addItem(withTitle: "Close", action: #selector(NSWindow.performClose(_:)), keyEquivalent: "w")
        menu.addItem(withTitle: "Window", action: nil, keyEquivalent: "").submenu = windowMenu
        NSApp.mainMenu = menu
        NSApp.windowsMenu = windowMenu
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        return model.requestQuit() == .quitNow ? .terminateNow : .terminateCancel
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        NSApp.terminate(nil)
        return false // Keep the window visible until an active operation finishes.
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag {
            window?.makeKeyAndOrderFront(nil)
        }
        return true
    }
}

#if !MANAGER_APP_TESTS
@main
struct DeadlockManagerApp {
    @MainActor static func main() {
        let app = NSApplication.shared
        let delegate = ManagerAppDelegate()
        app.setActivationPolicy(.regular)
        app.delegate = delegate
        withExtendedLifetime(delegate) { app.run() }
    }
}
#endif
