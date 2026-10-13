import SwiftUI
import AppKit

@MainActor
final class ManagerModel: ObservableObject {
    @Published var workspace = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Projects/Games/Deadlock").path
    @Published var profile = "highball"
    @Published var running = false
    @Published var status = "Ready to set up Windows Steam."
    @Published var output = ""
    @Published var gameModeTool = UserDefaults.standard.string(forKey: "gameModeTool") ?? ""
    @Published var testingGameMode = false
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

    func chooseWorkspace() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.canCreateDirectories = true
        panel.prompt = "Use folder"
        if panel.runModal() == .OK, let url = panel.url { workspace = url.path }
    }

    func run(_ command: [String], label: String) {
        guard !running, let resources = Bundle.main.resourceURL else { return }
        running = true
        testingGameMode = command.contains("game-mode") && command.contains("--test")
        status = label
        output = ""
        let selectedWorkspace = workspace
        let selectedProfile = profile
        Task.detached {
            let process = Process()
            process.executableURL = resources.appendingPathComponent("python/bin/python3")
            process.arguments = ["-I", "-B", resources.appendingPathComponent("launcher.py").path,
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
                await MainActor.run { self.activeProcess = process }
                while true {
                    let data = pipe.fileHandleForReading.availableData
                    if data.isEmpty { break }
                    let text = String(decoding: data, as: UTF8.self)
                    await MainActor.run { self.output += text }
                }
                process.waitUntilExit()
                let code = process.terminationStatus
                await MainActor.run {
                    self.running = false
                    self.testingGameMode = false
                    self.activeProcess = nil
                    let messages = ["bootstrap": "Steam installed. Open Steam and allow it to update.",
                                    "steam": "Steam is starting. First startup may take a few minutes before sign-in appears.",
                                    "install": "Install request sent. Complete the download in Steam.",
                                    "launch": "Play request sent. Check the game window.",
                                    "performance": "Settings saved. Restart Windows Steam for them to apply.",
                                    "graphics-preset": "Display settings saved with a backup. Verify them in the game.",
                                    "game-mode": "Game Mode operation finished. Check the policy in Details."]
                    self.status = code == 0 ? (messages[command.first ?? ""] ?? "Check complete.")
                        : "This step could not finish. See details below (code \(code))."
                }
            } catch {
                let message = error.localizedDescription
                await MainActor.run { self.running = false; self.testingGameMode = false; self.activeProcess = nil; self.status = message }
            }
        }
    }
}

struct ContentView: View {
    @StateObject private var model = ManagerModel()
    @State private var showDetails = true
    var body: some View {
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
                Button("Play") { model.run(["launch"], label: "Requesting game launch through Steam…") }
                Spacer()
            }.controlSize(.large).disabled(model.running)
            Text("Complete Steam Guard in Steam. Cloud support depends on the game; resolve any sync conflicts yourself.")
                .font(.caption).foregroundStyle(.secondary)
            HStack {
                Button("Check setup") { model.run(["doctor"], label: "Checking installation…") }
                Button("60 FPS + performance HUD") {
                    model.run(["performance", "--fps-cap", "60", "--hud", "on", "--hud-log", "on"], label: "Saving test settings…")
                }
                Button("1080p fullscreen") { model.run(["graphics-preset", "--apply"], label: "Backing up and updating display settings…") }
            }.disabled(model.running)
            Text("Exit Windows Steam before changing test settings. Apply 1080p after the game has run once.")
                .font(.caption).foregroundStyle(.secondary)
            GroupBox("Game Mode · optional comparison") {
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Button("Choose Apple tool…") { model.chooseGameModeTool() }.disabled(model.running)
                        Text(model.gameModeTool.isEmpty ? "Uses the selected Xcode's gamepolicyctl" : model.gameModeTool)
                            .font(.caption).lineLimit(1).truncationMode(.middle).textSelection(.enabled)
                    }
                    HStack {
                        Button("Check Game Mode") { model.gameMode() }.disabled(model.running)
                        Button("Test for 5 minutes") { model.gameMode(["--test", "--seconds", "300"]) }.disabled(model.running)
                        Button("Restore interrupted test") { model.gameMode(["--restore"]) }.disabled(model.running)
                        if model.testingGameMode {
                            Button("Stop test and restore") { model.stopGameModeTest() }
                        }
                    }
                    Text("Start Deadlock first. The test changes a system-wide policy, then restores it on game exit or timeout. Confirm On in the game HUD. A compatible Apple developer tool is required; normal Play works without it.")
                        .font(.caption).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
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
                }.frame(minHeight: 100, maxHeight: .infinity)
                    .background(.black.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))
            }
            Text("Experimental: startup/exit faults and performance are under investigation. This local build is not a signed, notarized player release.")
                .font(.caption).foregroundStyle(.secondary)
        }.padding(24).frame(minWidth: 800, minHeight: 800)
    }
}

@main
struct DeadlockManagerApp: App {
    var body: some Scene {
        WindowGroup { ContentView() }.windowResizability(.contentMinSize)
    }
}
