// Small, platform-independent lifecycle policy; exercised without launching a game.
enum ManagerQuitDecision {
    case quitNow, waitForOperation, stopDiagnosticAndWait
}

struct ManagerLifecycle {
    private(set) var command: [String]?
    private(set) var quitPending = false
    var running: Bool { command != nil }
    var testingGameMode: Bool {
        command?.first == "game-mode" && command?.contains("--test") == true
    }

    mutating func begin(_ command: [String]) -> Bool {
        guard !running, !command.isEmpty else { return false }
        self.command = command
        return true
    }

    mutating func requestQuit() -> ManagerQuitDecision {
        guard running else { return .quitNow }
        quitPending = true
        return testingGameMode ? .stopDiagnosticAndWait : .waitForOperation
    }

    // Failed operations keep the manager available to show errors/recovery steps.
    mutating func finish(success: Bool) -> (replyToQuit: Bool, shouldQuit: Bool) {
        let result = (replyToQuit: quitPending, shouldQuit: quitPending && success)
        command = nil
        quitPending = false
        return result
    }
}
