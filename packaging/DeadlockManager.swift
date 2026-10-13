import SwiftUI
import AppKit

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
    @Published var status = "Ready to set up Windows Steam."
    @Published var output = ""
    @Published var gameModeTool = UserDefaults.standard.string(forKey: "gameModeTool") ?? ""
    var testingGameMode: Bool { lifecycle.testingGameMode }
    @Published var automaticGameMode = UserDefaults.standard.object(forKey: "automaticGameMode") as? Bool ?? true {
        didSet { UserDefaults.standard.set(automaticGameMode, forKey: "automaticGameMode") }
    }
    private var activeProcess: Process?

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

    func stopGameModeTest() { activeProcess?.terminate() }

    func requestQuit() -> ManagerQuitDecision {
        let decision = lifecycle.requestQuit()
        switch decision {
        case .quitNow: break
        case .waitForOperation:
            status = "Finishing the current operation before quitting the manager…"
        case .stopDiagnosticAndWait:
            status = "Restoring Game Mode before quitting the manager…"
            stopGameModeTest()
        }
        return decision
    }

    private func finished(success: Bool) {
        activeProcess = nil
        let result = lifecycle.finish(success: success)
        if result.replyToQuit { NSApp.reply(toApplicationShouldTerminate: result.shouldQuit) }
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
        let selectedWorkspace = workspace
        let selectedProfile = profile
        Task.detached {
            let process = Process()
            process.executableURL = resources.appendingPathComponent("python/bin/python3")
            process.arguments = ["-I", "-B", "-u", resources.appendingPathComponent("launcher.py").path,
                                 "--workspace", selectedWorkspace, "--profile", selectedProfile] + command
            var env: [String: String] = ["PATH": "/usr/bin:/bin:/usr/sbin:/sbin"]
            for key in ["HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "LC_ALL"] {
                env[key] = ProcessInfo.processInfo.environment[key]
            }
            process.environment = env
            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = pipe
            process.standardInput = FileHandle.nullDevice
            do {
                try process.run()
                await MainActor.run {
                    self.activeProcess = process
                    if self.lifecycle.quitPending && self.testingGameMode { process.terminate() }
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
                    self.finished(success: code == 0)
                }
            } catch {
                let message = error.localizedDescription
                await MainActor.run { self.status = message; self.finished(success: false) }
            }
        }
    }
}

struct ContentView: View {
    @ObservedObject var model: ManagerModel
    @State private var showDetails = true
    @State private var displayMode = "borderless"
    @State private var displayWidth = ""
    @State private var displayHeight = ""
    var body: some View {
        ScrollView {
        VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top) {
                Image(systemName: "gamecontroller.fill").font(.system(size: 36)).foregroundStyle(.orange)
                VStack(alignment: .leading, spacing: 5) {
                    Text("Deadlock on Mac").font(.largeTitle.bold())
                    Text("Free runtime · Your Steam account").foregroundStyle(.secondary)
                }
                Spacer()
                Text("DEVELOPMENT PREVIEW").font(.caption.bold()).padding(8)
                    .background(.orange.opacity(0.12), in: RoundedRectangle(cornerRadius: 7))
            }
            Text("Install Windows Steam, sign into your existing account, then download and play Deadlock. Steam handles your library, updates and friends.")
                .fixedSize(horizontal: false, vertical: true)
            GroupBox("Installation folder") {
                HStack {
                    TextField("Deadlock workspace", text: $model.workspace)
                    Button("Choose…") { model.chooseWorkspace() }
                }.padding(5)
                HStack {
                    Text("Profile").foregroundStyle(.secondary)
                    TextField("Profile", text: $model.profile).frame(width: 170)
                    Spacer()
                    Text("Use a new folder for a clean installation.").font(.caption).foregroundStyle(.secondary)
                }.padding(5)
            }.disabled(model.running)
            HStack(spacing: 10) {
                Button("1. Set up Steam") { model.run(["bootstrap"], label: "Downloading verified components and installing Steam…") }
                    .buttonStyle(.borderedProminent)
                Button("2. Open Steam") { model.run(["steam"], label: "Opening Steam…") }
                Button("3. Install Deadlock") { model.run(["install"], label: "Opening Deadlock in Steam…") }
                Button("Play") { model.play() }
                Spacer()
            }.controlSize(.large).disabled(model.running)
            HStack {
                Button("Exit Deadlock") { model.run(["exit"], label: "Asking Steam to close Deadlock…") }.disabled(model.running)
                Button("Exit Windows Steam") { model.run(["steam-exit"], label: "Closing Deadlock and Windows Steam…") }.disabled(model.running)
                Spacer()
                Button("Quit Manager") { NSApp.terminate(nil) }
            }
            Text("Exit Windows Steam closes Deadlock first. Quit Manager leaves Steam and the game running; Game Mode still restores when the game exits.")
                .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            Text("Complete Steam Guard in Steam. Cloud support depends on the game; resolve any sync conflicts yourself.")
                .font(.caption).foregroundStyle(.secondary)
            HStack {
                Button("Check setup") { model.run(["doctor"], label: "Checking installation…") }
                Button("60 FPS + performance HUD") {
                    model.run(["performance", "--fps-cap", "60", "--hud", "on", "--hud-log", "on"], label: "Saving test settings…")
                }
                Button("Set game and menu limits to 60 FPS") {
                    model.run(["game-fps", "--cap", "60", "--menu-cap", "60", "--apply"], label: "Backing up and saving game FPS limits…")
                }
            }.disabled(model.running)
            GroupBox("Display settings") {
                HStack {
                    Picker("Mode", selection: $displayMode) {
                        Text("Fullscreen").tag("fullscreen")
                        Text("Borderless").tag("borderless")
                    }.frame(width: 210)
                    TextField("Width", text: $displayWidth).frame(width: 70)
                    Text("×")
                    TextField("Height", text: $displayHeight).frame(width: 70)
                    Button("Preview") {
                        model.run(["graphics-preset", "--mode", displayMode, "--width", displayWidth, "--height", displayHeight], label: "Previewing display changes…")
                    }
                    Button("Apply with backup") {
                        model.run(["graphics-preset", "--mode", displayMode, "--width", displayWidth, "--height", displayHeight, "--apply"], label: "Backing up and updating display settings…")
                    }
                }.padding(5).disabled(model.running)
                Text("Close Windows Steam before applying. Use a resolution supported by your display; graphics quality and render scale are preserved.")
                    .font(.caption).foregroundStyle(.secondary)
                HStack {
                    Button("Retina status") { model.run(["retina"], label: "Reading Wine Retina setting…") }
                    Button("Enable Retina") { model.run(["retina", "--set", "on", "--apply"], label: "Backing up and enabling Retina…") }
                    Button("Disable Retina") { model.run(["retina", "--set", "off", "--apply"], label: "Backing up and disabling Retina…") }
                }.padding(5).disabled(model.running)
                Text("Experimental: Retina exposes full pixel resolution for high-resolution borderless play. Requires Steam closed and affects this whole Wine bottle. Verify screen coverage, pointer alignment and app switching after restart.")
                    .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }
            DisclosureGroup("Wine exit hotfix") {
                HStack {
                    Button("Check hotfix") { model.run(["wine-hotfix"], label: "Verifying Wine exit hotfix…") }
                    Button("Enable") { model.run(["wine-hotfix", "--set", "on"], label: "Enabling verified hotfix…") }
                    Button("Roll back") { model.run(["wine-hotfix", "--set", "off"], label: "Disabling hotfix…") }
                }.disabled(model.running)
                Text("Close Windows Steam before changing the hotfix. The original Wine engine stays intact.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Text("Exit Windows Steam before changing test settings. Display settings are available after the game has run once.")
                .font(.caption).foregroundStyle(.secondary)
            GroupBox("Game Mode") {
                VStack(alignment: .leading, spacing: 8) {
                    Toggle("Enable during Play, then restore when Deadlock exits", isOn: $model.automaticGameMode)
                        .disabled(model.running)
                    HStack {
                        Button("Choose Apple tool…") { model.chooseGameModeTool() }.disabled(model.running)
                        Text(model.gameModeTool.isEmpty ? "Uses the selected Xcode's gamepolicyctl" : model.gameModeTool)
                            .font(.caption).lineLimit(1).truncationMode(.middle).textSelection(.enabled)
                    }
                    HStack {
                        Button("Check Game Mode") { model.gameMode() }.disabled(model.running)
                        Button("Play session status") { model.gameMode(["--session"]) }.disabled(model.running)
                        Button("Recover interrupted Play") { model.gameMode(["--restore-session"]) }.disabled(model.running)
                        Button("End session and restore") { model.gameMode(["--stop-session"]) }.disabled(model.running)
                        if model.testingGameMode {
                            Button("Stop test and restore") { model.stopGameModeTest() }
                        }
                    }
                    Text("Play keeps Game Mode on until the game exits, with no time limit. You can close this manager. The previous system-wide policy is restored afterward. Choose a compatible Apple tool and confirm On in the game HUD.")
                        .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                    DisclosureGroup("Timed diagnostic (separate from Play)") {
                        HStack {
                            Button("Test for 5 minutes") { model.gameMode(["--test", "--seconds", "300"]) }.disabled(model.running)
                            Button("Restore interrupted test") { model.gameMode(["--restore"]) }.disabled(model.running)
                        }
                    }.font(.caption)
                }.padding(5)
            }
            HStack {
                if model.running { ProgressView().controlSize(.small) }
                Text(model.status).font(.callout).textSelection(.enabled)
                Spacer()
            }
            DisclosureGroup("Details", isExpanded: $showDetails) {
                ScrollView {
                    Text(model.output.isEmpty ? "No operation has run in this window." : model.output)
                        .font(.system(.caption, design: .monospaced)).textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading).padding(10)
                }.frame(height: 180)
                    .background(.black.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))
            }
            Text("Experimental: display compatibility and sustained performance remain under investigation. This local build is ad-hoc signed, not notarized for public distribution.")
                .font(.caption).foregroundStyle(.secondary)
        }.padding(24).frame(maxWidth: .infinity, alignment: .leading)
        }.frame(minWidth: 800, minHeight: 740)
    }
}

@main
struct DeadlockManagerApp: App {
    @NSApplicationDelegateAdaptor(ManagerAppDelegate.self) private var appDelegate
    @StateObject private var model = ManagerModel()
    var body: some Scene {
        Window("Deadlock Manager", id: "manager") {
            ContentView(model: model)
                .background(WindowAttachment(delegate: appDelegate))
                .onAppear { appDelegate.model = model }
        }.windowResizability(.contentMinSize)
    }
}

@MainActor
final class ManagerAppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    weak var model: ManagerModel?

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let model else { return .terminateNow }
        return model.requestQuit() == .quitNow ? .terminateNow : .terminateLater
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        NSApp.terminate(nil)
        return false // Keep the window visible until an active operation finishes.
    }
}

private struct WindowAttachment: NSViewRepresentable {
    let delegate: ManagerAppDelegate
    func makeNSView(context: Context) -> AttachedView { AttachedView(delegate: delegate) }
    func updateNSView(_ nsView: AttachedView, context: Context) {}

    final class AttachedView: NSView {
        let managerDelegate: ManagerAppDelegate
        init(delegate: ManagerAppDelegate) {
            managerDelegate = delegate
            super.init(frame: .zero)
        }
        required init?(coder: NSCoder) { fatalError("init(coder:) is unavailable") }
        override func viewDidMoveToWindow() {
            super.viewDidMoveToWindow()
            window?.delegate = managerDelegate
        }
    }
}
