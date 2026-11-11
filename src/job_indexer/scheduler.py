from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any


def run_schedule(
    task: Callable[[], Any],
    interval_seconds: float,
    *,
    run_immediately: bool = True,
    max_runs: int | None = None,
    stop_event: threading.Event | None = None,
    on_cycle: Callable[[int, Any], None] | None = None,
) -> int:
    if interval_seconds < 0:
        raise ValueError("interval_seconds must be non-negative")
    if max_runs is not None and max_runs < 1:
        raise ValueError("max_runs must be at least 1")

    stop = stop_event or threading.Event()
    runs = 0
    if not run_immediately:
        if stop.wait(interval_seconds):
            return 0

    while not stop.is_set():
        result = task()
        runs += 1
        if on_cycle is not None:
            on_cycle(runs, result)
        if max_runs is not None and runs >= max_runs:
            break
        if stop.wait(interval_seconds):
            break
    return runs
