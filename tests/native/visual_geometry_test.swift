import Foundation

@main struct VisualGeometryTests {
    static func main() throws {
        let frame = CGRect(x: 1512, y: -458, width: 2560, height: 1440)
        let info: [String: Any] = ["bounds": VisualGeometry.bounds(frame)]
        let encoded = try JSONSerialization.data(withJSONObject: info)
        let decoded = try JSONSerialization.jsonObject(with: encoded) as! [String: Any]
        // CGFloat arrays serialized correctly but failed the in-process [Double]
        // cast, rejecting every real input. Exercise that exact boundary.
        precondition(info["bounds"] as? [Double] == decoded["bounds"] as? [Double])
        precondition(info["bounds"] as? [Double] != nil)
        precondition(VisualGeometry.contentWindow(layer: 26, width: 2560, height: 1440))
        precondition(VisualGeometry.contentWindow(layer: 0, width: 1280, height: 800))
        precondition(!VisualGeometry.contentWindow(layer: 0, width: 2560, height: 30))
        precondition(!VisualGeometry.contentWindow(layer: 101, width: 2560, height: 1440))
        let retina = try VisualGeometry.point(x: 1512, y: 982, pixels: [3024,1964], frame: [0,0,1512,982])
        precondition(retina.x == 756 && retina.y == 491)
        let lg = try VisualGeometry.point(x: 1280, y: 720, pixels: [2560,1440], frame: [1512,-458,2560,1440])
        precondition(lg.x == 2792 && lg.y == 262)
        let left = try VisualGeometry.point(x: 400,y: 200,pixels:[1600,900],frame:[-1600,-900,1600,900])
        precondition(left.x == -1200 && left.y == -700)
        for (x,y) in [(-1.0,0.0),(2560,0),(0,1440),(Double.nan,0),(Double.infinity,0)] {
            do { _ = try VisualGeometry.point(x:x,y:y,pixels:[2560,1440],frame:[1512,-458,2560,1440]); fatalError("Accepted invalid point") }
            catch { }
        }
        for (key, duration) in [("w", 0), ("w", 1001), ("escape", 500), ("q", 500)] {
            do { _ = try VisualKeyHold.duration(key: key, command: "key", milliseconds: duration); fatalError("Accepted invalid hold") }
            catch { }
        }
        let duration = try VisualKeyHold.duration(key: "w", command: "key", milliseconds: 1000)
        precondition(duration == 1000)
        var events: [String] = [], elapsed = 0
        try VisualKeyHold.run(milliseconds: 1000, press: { events.append("down") }, release: { events.append("up") },
                              validate: {}, pause: { elapsed += $0 })
        precondition(events == ["down", "up"] && elapsed == 1000)
        events = []; elapsed = 0
        do {
            try VisualKeyHold.run(milliseconds: 1000, press: { events.append("down") }, release: { events.append("up") }, validate: {
                if elapsed >= 40 { throw VisualFailure.message("Focus changed or grant revoked") }
            }, pause: { elapsed += $0 })
            fatalError("Ignored lost focus")
        } catch { }
        precondition(events == ["down", "up"] && elapsed == 40)
        events = []
        do {
            try VisualKeyHold.run(milliseconds: 1000, press: { events.append("down") }, release: { events.append("up") },
                                  validate: { throw VisualFailure.message("Already revoked") }, pause: { _ in })
            fatalError("Ignored revoked grant")
        } catch { }
        precondition(events.isEmpty)
        print("PASS bounded movement: release on completion/lost focus/revocation; no press when already revoked")
        print("PASS visual coordinate mapping: Retina, external, negative origins, bounds and nonfinite rejection")
    }
}
