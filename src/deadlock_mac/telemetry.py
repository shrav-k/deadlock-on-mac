"""Analyze a single process's Metal HUD presentation samples from a private log."""
from datetime import datetime
import math
import re
import statistics

from .storage import ManagerError

HUD = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+) .*\[(\d+):\d+\] metal-HUD: (.+)$')


def summarize(lines, pid, warmup_seconds=0, start_time=None, end_time=None):
    if type(pid) is not int or pid <= 0 or not math.isfinite(warmup_seconds) or warmup_seconds < 0:
        raise ManagerError("A positive game PID and nonnegative warm-up duration are required.")
    try:
        start = datetime.fromisoformat(start_time) if start_time is not None else None
        end = datetime.fromisoformat(end_time) if end_time is not None else None
    except (ValueError, TypeError) as exc:
        raise ManagerError("Use local ISO timestamps, such as 2026-10-13T12:30:00.") from exc
    if any(t is not None and t.tzinfo is not None for t in (start, end)):
        raise ManagerError("Metal HUD timestamps use local time without a UTC offset.")
    if start is not None and end is not None and start >= end:
        raise ManagerError("The report end must be after its start.")
    intervals, gpu_times, timestamps, seen = [], [], [], set()
    first = start
    for line in lines:
        match = HUD.match(line.strip())
        if not match or int(match[2]) != pid:
            continue
        try:
            stamp = datetime.fromisoformat(match[1])
            values = [float(v) for v in match[3].split(",")]
        except ValueError:
            continue
        # Three HUD metadata values precede (present interval ms, GPU ms) pairs.
        # These are presentation samples, not proven unique game simulation frames.
        if len(values) < 5 or (len(values) - 3) % 2 or not all(math.isfinite(v) for v in values):
            continue
        if (start is not None and stamp < start) or (end is not None and stamp >= end):
            continue
        if first is None:
            first = stamp
        if (stamp - first).total_seconds() < warmup_seconds or (stamp, match[3]) in seen:
            continue
        seen.add((stamp, match[3]))
        timestamps.append(stamp)
        for interval, gpu in zip(values[3::2], values[4::2]):
            if interval > 0 and gpu >= 0:
                intervals.append(interval)
                gpu_times.append(gpu)
    if not intervals:
        raise ManagerError("No valid Metal HUD samples for that PID after warm-up. Enable HUD logging before restarting Steam; do not infer FPS from process lifetime.")
    ordered = sorted(intervals)
    percentile = lambda q: ordered[max(0, math.ceil(len(ordered) * q) - 1)]
    return {"pid": pid, "hud_records": len(seen), "presentation_samples": len(intervals),
            "record_span_seconds": round((max(timestamps) - min(timestamps)).total_seconds(), 3),
            "warmup_seconds_excluded": warmup_seconds,
            "start_time": start_time, "end_time": end_time,
            "mean_presentation_fps": round(1000 / statistics.mean(intervals), 2),
            "median_interval_ms": round(statistics.median(intervals), 3),
            "p95_interval_ms": round(percentile(.95), 3), "p99_interval_ms": round(percentile(.99), 3),
            "max_interval_ms": round(max(intervals), 3),
            "samples_over_33_33_ms": sum(v > 1000 / 30 for v in intervals),
            "mean_gpu_ms": round(statistics.mean(gpu_times), 3),
            "scope": "Metal HUD presentation interval samples for one process; not unique simulation frames or a match benchmark. Time filters select log records, whose samples can precede their timestamp. Loading and focus-loss gaps remain included."}
