from __future__ import annotations

import threading

import pytest

from job_indexer.scheduler import run_schedule


def test_run_schedule_runs_immediately_and_stops_after_max_runs() -> None:
    calls = []

    def task() -> str:
        calls.append("run")
        return "ok"

    cycles = []
    runs = run_schedule(
        task,
        0,
        max_runs=2,
        on_cycle=lambda number, result: cycles.append((number, result)),
    )

    assert runs == 2
    assert calls == ["run", "run"]
    assert cycles == [(1, "ok"), (2, "ok")]


def test_run_schedule_can_wait_before_first_run() -> None:
    calls = []
    stop = threading.Event()
    stop.set()

    runs = run_schedule(
        lambda: calls.append("run"),
        0,
        run_immediately=False,
        stop_event=stop,
    )

    assert runs == 0
    assert calls == []


def test_run_schedule_stops_when_event_is_set() -> None:
    stop = threading.Event()
    calls = []

    def task() -> None:
        calls.append("run")
        stop.set()

    runs = run_schedule(task, 0, stop_event=stop)

    assert runs == 1
    assert calls == ["run"]


@pytest.mark.parametrize("interval", [-1, -0.1])
def test_run_schedule_rejects_negative_interval(interval: float) -> None:
    with pytest.raises(ValueError, match="interval_seconds"):
        run_schedule(lambda: None, interval)


def test_run_schedule_rejects_zero_max_runs() -> None:
    with pytest.raises(ValueError, match="max_runs"):
        run_schedule(lambda: None, 0, max_runs=0)
