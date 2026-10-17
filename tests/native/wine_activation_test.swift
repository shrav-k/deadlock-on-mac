import Foundation

@main struct ActivationTests {
    static func main() {
        let now = Date()
        var grant = WineActivationGrant(prefix: "/bottle", runtime: URL(fileURLWithPath: "/owned/engine"),
                                        expires: now.addingTimeInterval(180))
        func executable(_ path: String = "/owned/engine/bin/wine64-preloader") -> URL { URL(fileURLWithPath: path) }
        precondition(!grant.accept(pid: 42, prefix: "/other-bottle", executable: executable(), active: true, now: now))
        precondition(!grant.accept(pid: 42, prefix: "/bottle", executable: executable(), active: false, now: now))
        precondition(!grant.accept(pid: 42, prefix: "/bottle", executable: nil, active: true, now: now))
        precondition(!grant.accept(pid: 42, prefix: "/bottle", executable: executable("/owned/engine-evil/bin/wine"), active: true, now: now))
        precondition(!grant.accept(pid: 42, prefix: "/bottle", executable: executable("/owned/engine/bin/unrelated"), active: true, now: now))
        precondition(!grant.accept(pid: 42, prefix: "/bottle", executable: executable(), active: true, now: now.addingTimeInterval(180)))
        precondition(grant.accept(pid: 42, prefix: "/bottle", executable: executable(), active: true, now: now))
        precondition(!grant.accept(pid: 42, prefix: "/bottle", executable: executable(), active: true, now: now))
        precondition(grant.accept(pid: 43, prefix: "/bottle", executable: executable(), active: true, now: now))
        print("PASS activation grant: prefix, executable boundary, expiry, foreground requirement, one handoff per PID")
    }
}
