import SwiftUI
import AppKit

struct ConnectedDisplay: Identifiable, Decodable {
    let id: String
    let name: String
    let main: Bool
    let builtin: Bool
    let mode_pixels: [Int]
    var label: String { "\(name) · \(mode_pixels.map(String.init).joined(separator: "×"))\(main ? " · Main" : "")" }
}

struct DisplaySelection: Decodable {
    let phase: String
    let choice: String?
    let retina_policy: String?
    let target_name: String?
}

struct DisplayReport: Decodable {
    let displays: [ConnectedDisplay]
    let selection: DisplaySelection?
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
    @Published private(set) var operationStartedAt: Date?
    @Published var gameModeTool = UserDefaults.standard.string(forKey: "gameModeTool") ?? ""
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

    func refreshDisplays() { run(["display"], label: "Reading connected displays…") }

    var displayPrepareArguments: [String] { ["display", "--prepare", displayChoice, "--retina", retinaPolicy] }
    func prepareDisplay() {
        run(displayPrepareArguments, label: "Preparing the selected display; keep Steam closed…")
    }

    func readDisplayReport() {
        guard let data = output.data(using: .utf8),
              let report = try? JSONDecoder().decode(DisplayReport.self, from: data) else { return }
        displays = report.displays
        displayChoice = report.selection?.choice ?? "default"
        retinaPolicy = report.selection?.retina_policy ?? "auto"
        if let selected = report.selection, selected.phase == "ready" {
            if !["default", "external"].contains(displayChoice) && !displays.contains(where: { $0.id == displayChoice }) {
                displaySummary = "\(selected.target_name ?? "Saved display") is disconnected. Choose a connected display in Settings and apply it."
            } else {
                displaySummary = "Prepared: \(selected.target_name ?? displayChoice). Play checks for display and settings changes."
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
        var arguments = ["launch"]
        if !automaticGameMode { arguments += ["--without-game-mode"] }
        else if !gameModeTool.isEmpty { arguments += ["--game-mode-tool", gameModeTool] }
        run(arguments, label: "Starting Deadlock through Steam…")
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
                                    "launch": "Play request sent. Check the game window.",
                                    "exit": "Deadlock is closed. Steam remains open; check Details for Game Mode restoration.",
                                    "steam-exit": "Windows Steam is closed. Check Details for Game Mode restoration.",
                                    "performance": "Settings saved. Restart Windows Steam for them to apply.",
                                    "graphics-preset": "Display settings saved with a backup. Verify them in the game.",
                                    "game-mode": "Game Mode operation finished. Check the policy in Details."]
                    self.status = code == 0 ? (messages[command.first ?? ""] ?? "Check complete.")
                        : "This step could not finish. See details below (code \(code))."
                    if code == 0 && command == ["display"] { self.readDisplayReport() }
                    if code == 0 && command.contains("--prepare") {
                        self.displaySummary = "Display prepared. Open Steam, then Play; check the game menu before gameplay."
                    }
                    if code == 0 && command.contains("--clear") {
                        self.displaySummary = "Display management is off; current game and Retina settings were preserved."
                    }
                    self.finished(success: code == 0)
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
            GroupBox {
                VStack(alignment: .leading, spacing: 14) {
                    Label(model.displaySummary, systemImage: "display")
                    Label(model.automaticGameMode ? "Game Mode enabled during Play" : "Automatic Game Mode disabled", systemImage: "speedometer")
                    Text("Game Mode restores after Deadlock exits. Quitting this manager leaves the game and Steam running.")
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
                    Text("Match selected display").tag("auto")
                    Text("On").tag("on"); Text("Off").tag("off")
                }
                HStack {
                    Button("Refresh") { model.refreshDisplays() }
                    Button("Apply Display") { model.prepareDisplay() }
                }
                Text(model.displaySummary).font(.caption)
                Text("Close Windows Steam before applying. Saves a backup, sets borderless output and matches Wine scaling to this display. Your macOS main display stays unchanged.")
                    .font(.caption).foregroundStyle(.secondary)
            }.padding(8)
        }.disabled(model.running)
        GroupBox("Game Mode") {
            VStack(alignment: .leading, spacing: 10) {
                Toggle("Enable during Play and restore on exit", isOn: $model.automaticGameMode)
                Text("No time limit. The Play watcher continues if you close the manager.").font(.caption).foregroundStyle(.secondary)
                DisclosureGroup("Apple tool") {
                    HStack {
                        Button("Choose…") { model.chooseGameModeTool() }
                        Text(model.gameModeTool.isEmpty ? "Selected Xcode toolchain" : model.gameModeTool)
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
                    Button("Set Up Steam") { model.run(["bootstrap"], label: "Installing verified components and Steam…") }
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
        DisclosureGroup("Wine exit hotfix") {
            HStack {
                Button("Check") { model.run(["wine-hotfix"], label: "Verifying Wine exit hotfix…") }
                Button("Enable") { model.run(["wine-hotfix", "--set", "on"], label: "Enabling verified hotfix…") }
                Button("Roll Back") { model.run(["wine-hotfix", "--set", "off"], label: "Disabling hotfix…") }
            }.padding(.top, 8).disabled(model.running)
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
