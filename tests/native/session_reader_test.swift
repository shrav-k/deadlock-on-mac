import Foundation

@main struct SessionReaderTests {
    static func main() throws {
        let resources = URL(fileURLWithPath: CommandLine.arguments[1])
        let workspace = CommandLine.arguments[2]
        let fixture = URL(fileURLWithPath: workspace).appendingPathComponent("session-fixture.json")
        func read() -> String { PlaySessionReader.read(resources: resources, workspace: workspace, profile: "highball") }
        precondition(read() == "No tracked Play session.")
        let data: [String: Any] = ["workspace": workspace, "profile": "highball", "phase": "finished",
                                  "restore_pending": false, "watcher_running": false, "error": "Steam stalled"]
        try JSONSerialization.data(withJSONObject: data).write(to: fixture)
        precondition(read().contains("Play session failed: Steam stalled"), "Read the detached outcome after dispatch succeeded")
        precondition(read().contains("Previous Game Mode policy restored"))
        try Data("malformed".utf8).write(to: fixture)
        precondition(read().contains("could not be read"), "Malformed state is not a launch pass")
        try Data(repeating: 65, count: 100_000).write(to: fixture)
        precondition(read().contains("could not be read"), "Bound output from a faulty helper")
        precondition(!FileManager.default.fileExists(atPath: URL(fileURLWithPath: workspace).appendingPathComponent("worker-finished").path))
        print("PASS isolated session reader: idle, delayed failure/restoration, malformed/oversized output; no launch or policy mutation")
    }
}
