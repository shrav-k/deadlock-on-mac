import AppKit
import Foundation

// This test runs the real app delegate, owned window, model and Process runner.
// The isolated test bundle supplies a fake CLI; it never starts Wine or Steam.
@main
struct ManagerAppTests {
    @MainActor static func main() {
        let scenario = CommandLine.arguments[1]
        let workspace = CommandLine.arguments[2]
        let app = NSApplication.shared
        let delegate = ManagerAppDelegate(presentWindow: false)
        app.setActivationPolicy(.prohibited)
        app.delegate = delegate
        let marker = URL(fileURLWithPath: workspace).appendingPathComponent("worker-finished")
        var requested = false
        let shouldFail = scenario.contains("failure")
        let idle = scenario == "idle-close"
        let diagnostic = scenario.contains("diagnostic")
        let observer = NotificationCenter.default.addObserver(forName: NSApplication.willTerminateNotification,
                                                               object: app, queue: .main) { _ in
            MainActor.assumeIsolated {
                precondition(requested, "Unexpected app termination")
                precondition(!shouldFail, "Failed operation must leave the manager open")
                precondition(!delegate.model.running, "Quit orphaned an active worker")
                if !idle {
                    let text = try! String(contentsOf: marker, encoding: .utf8)
                    precondition(text == (diagnostic ? "restored" : "success"))
                    precondition(delegate.model.output.contains("worker cleanup complete"))
                }
                print("PASS \(scenario)")
            }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            precondition(delegate.window?.delegate === delegate)
            delegate.model.workspace = workspace
            if !idle {
                delegate.model.run(diagnostic ? ["game-mode", "--test"] : [shouldFail ? "failure" : "steam-exit"],
                                   label: "Test operation")
            }
            let request = {
                requested = true
                if scenario.contains("close") {
                    // Use the actual AppKit close button, not just the policy object.
                    delegate.window!.standardWindowButton(.closeButton)!.performClick(nil)
                } else {
                    app.terminate(nil) // The production Command-Q/menu action.
                }
                if !idle {
                    precondition(delegate.model.running, "Worker unexpectedly finished before the test request")
                    precondition(delegate.model.status.contains(diagnostic ? "Restoring" : "Finishing"))
                }
            }
            if scenario == "diagnostic-before-spawn" { request() }
            else { DispatchQueue.main.asyncAfter(deadline: .now() + 0.35, execute: request) }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
            // An immediate cancellation may arrive before Python installs its
            // cleanup handler. No diagnostic started in that case; the safe
            // outcome is a visible startup failure, not a claimed restoration.
            let cancelledBeforeStart = scenario == "diagnostic-before-spawn"
                && !FileManager.default.fileExists(atPath: marker.path)
            if shouldFail || cancelledBeforeStart {
                precondition(requested && !delegate.model.running)
                precondition(delegate.model.status.contains("could not finish"))
                precondition(delegate.window?.delegate === delegate)
                if shouldFail { precondition(FileManager.default.fileExists(atPath: marker.path)) }
                print("PASS \(scenario): failure remains available")
                exit(0)
            }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 8) {
            fputs("FAIL \(scenario): app/worker completion stalled\n", stderr)
            exit(1)
        }
        withExtendedLifetime((delegate, observer)) { app.run() }
    }
}
