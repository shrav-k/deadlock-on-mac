import AppKit

// A user-initiated launch may hand focus to the selected Wine engine for a short
// startup interval. This is not a window mover, global focus loop or Spaces edit.
struct WineActivationGrant {
    let prefix: String
    let runtime: URL
    let expires: Date
    private(set) var acceptedPIDs: Set<pid_t> = []

    mutating func accept(pid: pid_t, prefix: String, executable: URL?, active: Bool,
                         now: Date = Date()) -> Bool {
        guard active, now < expires, pid > 0, !acceptedPIDs.contains(pid), self.prefix == prefix,
              let executable else { return false }
        let root = runtime.resolvingSymlinksInPath().path + "/"
        let path = executable.resolvingSymlinksInPath().path
        guard path.hasPrefix(root), ["wine", "wine64", "wine-preloader", "wine64-preloader"].contains(executable.lastPathComponent)
        else { return false }
        acceptedPIDs.insert(pid)
        return true
    }
}

@MainActor
final class WineActivationHandoff {
    private var observer: NSObjectProtocol?
    private var grant: WineActivationGrant?

    func arm(workspace: String, profile: String, command: [String], report: @escaping (String) -> Void) {
        cancel()
        guard ["steam", "launch", "install"].contains(command.first ?? "") || (command.first == "display" && command.contains("--test-window"))
        else { return }
        guard profile.range(of: "^[A-Za-z0-9][A-Za-z0-9._-]*$", options: .regularExpression) != nil else { return }
        let path = URL(fileURLWithPath: workspace).appendingPathComponent("DeadlockData/profiles/\(profile).json")
        guard let data = try? Data(contentsOf: path),
              let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              value["provider"] as? String == "wine",
              let prefix = value["prefix"] as? String, prefix.hasPrefix("/"),
              let runtime = value["runtime"] as? String, runtime.hasPrefix("/") else { return }
        grant = WineActivationGrant(prefix: prefix, runtime: URL(fileURLWithPath: runtime),
                                    expires: Date().addingTimeInterval(180))
        observer = DistributedNotificationCenter.default().addObserver(
            forName: Notification.Name("WineAppWillActivateNotification"), object: nil, queue: .main
        ) { [weak self] note in
            MainActor.assumeIsolated {
                guard let self, let pid = note.userInfo?["ActivatingAppPID"] as? NSNumber,
                      let prefix = note.userInfo?["ActivatingAppPrefix"] as? String,
                      let app = NSRunningApplication(processIdentifier: pid.int32Value),
                      !app.isTerminated,
                      self.grant?.accept(pid: pid.int32Value, prefix: prefix, executable: app.executableURL,
                                         active: NSApp.isActive) == true else { return }
                NSApp.yieldActivation(to: app)
                let accepted = app.activate(from: .current, options: [])
                report("Window activation handoff to Wine PID \(pid): \(accepted ? "accepted" : "not accepted"). Verify the window is visible.\n")
            }
        }
    }

    func cancel() {
        if let observer { DistributedNotificationCenter.default().removeObserver(observer) }
        observer = nil
        grant = nil
    }
}
