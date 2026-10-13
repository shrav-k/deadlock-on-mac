@main
struct LifecycleTests {
    static func main() {
        var state = ManagerLifecycle()
        precondition(state.requestQuit() == .quitNow)
        precondition(!state.begin([]))
        precondition(state.begin(["steam-exit"]))
        precondition(!state.begin(["launch"]))
        precondition(state.requestQuit() == .waitForOperation)
        let success = state.finish(success: true)
        precondition(success.replyToQuit && success.shouldQuit && !state.running)
        precondition(state.begin(["bootstrap"]))
        precondition(state.requestQuit() == .waitForOperation)
        let failure = state.finish(success: false)
        precondition(failure.replyToQuit && !failure.shouldQuit && !state.quitPending)
        precondition(state.begin(["game-mode", "--test", "--seconds", "300"]))
        precondition(state.requestQuit() == .stopDiagnosticAndWait)
        precondition(state.testingGameMode)
        precondition(state.finish(success: true).shouldQuit)
        precondition(state.begin(["launch"]))
        precondition(!state.finish(success: true).replyToQuit)
        precondition(state.requestQuit() == .quitNow)
        print("Manager lifecycle tests passed (idle, busy, failure, diagnostic restoration, duplicate operation).")
    }
}
