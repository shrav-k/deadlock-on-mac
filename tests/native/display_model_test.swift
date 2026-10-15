import Foundation

@main struct DisplayModelTests {
    @MainActor static func main() {
        let model = ManagerModel()
        model.output = #"{"displays":[{"id":"lg-id","name":"LG ULTRAGEAR","main":false,"builtin":false,"mode_pixels":[2560,1440]}],"selection":{"phase":"ready","choice":"lg-id","retina_policy":"auto","target_name":"LG ULTRAGEAR"}}"#
        model.readDisplayReport()
        precondition(model.displays.count == 1 && !model.displays[0].main)
        precondition(model.displays[0].label.contains("2560×1440"))
        precondition(model.displayChoice == "lg-id")
        precondition(model.displayPrepareArguments == ["display", "--prepare", "lg-id", "--retina", "auto"])
        precondition(model.displaySummary.contains("Prepared: LG ULTRAGEAR"))
        model.output = #"{"displays":[],"selection":{"phase":"ready","choice":"missing-id","retina_policy":"off","target_name":"LG ULTRAGEAR"}}"#
        model.readDisplayReport()
        precondition(model.displayChoice == "missing-id", "Disconnected target must not silently switch")
        precondition(model.retinaPolicy == "off")
        model.output = #"{"displays":[],"selection":null}"#
        model.readDisplayReport()
        precondition(model.displayChoice == "default" && model.retinaPolicy == "auto")
        model.output = "Malformed helper output"
        model.readDisplayReport()
        precondition(model.displayChoice == "default")
        print("PASS display picker model: names, saved identity, preparation argv, disconnected target, defaults")
    }
}
