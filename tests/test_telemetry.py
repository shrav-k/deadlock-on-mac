import unittest
from deadlock_mac.telemetry import summarize
from deadlock_mac.storage import ManagerError


class TelemetryTests(unittest.TestCase):
    def test_rounded_60_fps_intervals_are_not_counted_as_over_16_67_ms(self):
        row = "2026-10-13 11:00:00.000 wine[123:1] metal-HUD: 1,0,44,16.67,3,33.33,4,51,8\n"
        result = summarize([row], 123)
        self.assertEqual(result["samples_over_16_67_ms"], 2)
        self.assertEqual(result["samples_over_33_33_ms"], 1)
        self.assertEqual(result["p99_9_interval_ms"], 51)
        self.assertEqual(result["slowest_one_percent_mean_interval_ms"], 51)

    def test_filter_process_exclude_warmup_and_ignore_malformed_lines(self):
        rows = ["2026-10-13 11:00:00.000 wine[123:1] metal-HUD: 1,0,44,100,3\n",
                "2026-10-13 11:00:10.000 wine[456:1] metal-HUD: 2,0,44,1000,3\n",
                "2026-10-13 11:00:10.000 wine[123:1] metal-HUD: 3,0,44,10,2,20,4\n",
                "2026-10-13 11:00:11.000 wine[123:1] metal-HUD: 4,0,44<private>\n",
                "2026-10-13 11:00:11.000 wine[123:1] metal-HUD: 4,0,44,nan,2\n"]
        result = summarize(rows + rows[2:3], 123, 5)
        self.assertEqual(result["presentation_samples"], 2)
        self.assertEqual(result["mean_presentation_fps"], 66.67)
        self.assertEqual(result["p99_interval_ms"], 20)
        self.assertEqual(result["mean_gpu_ms"], 3)
        self.assertEqual(result["hud_records"], 1)

    def test_missing_or_invalid_samples_never_become_zero_fps(self):
        for pid, warmup in ((123, 0), (0, 0), (123, -1), (123, float("nan"))):
            with self.assertRaises(ManagerError):
                summarize([], pid, warmup)

    def test_gameplay_segment_excludes_menu_warmup_and_later_settings(self):
        rows = [f"2026-10-13 12:{minute}:00.000 wine[123:1] metal-HUD: 1,0,44,{ms},3\n"
                for minute, ms in (("00", 1000), ("01", 500), ("02", 20), ("03", 1000))]
        result = summarize(rows, 123, 60, "2026-10-13T12:01:00", "2026-10-13T12:03:00")
        self.assertEqual(result["hud_records"], 1)
        self.assertEqual(result["mean_presentation_fps"], 50)
        for start, end in (("bad", None), ("2026-10-13T12:00:00Z", None),
                           ("2026-10-13T12:03:00", "2026-10-13T12:01:00")):
            with self.assertRaises(ManagerError):
                summarize(rows, 123, 0, start, end)
