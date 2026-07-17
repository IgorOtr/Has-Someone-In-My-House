"""Tests for web.monitor_process using a harmless dummy subprocess.

None of these tests spawn the real ``run.py`` (no webcam, no model): a
short Python script standing in for the monitor is used instead so the
process start/stop/signal-handling logic can be exercised for real.
"""

import sys
import time

import pytest

from web.monitor_process import (
    MonitorAlreadyRunningError,
    MonitorNotRunningError,
    MonitorProcessManager,
)

_SLEEPY_SCRIPT = (
    "import signal, sys, time\n"
    "signal.signal(signal.SIGINT, lambda *_: sys.exit(0))\n"
    "time.sleep(30)\n"
)


def make_manager() -> MonitorProcessManager:
    return MonitorProcessManager(command=[sys.executable, "-c", _SLEEPY_SCRIPT])


def test_not_running_before_start():
    manager = make_manager()

    assert manager.is_running() is False
    assert manager.pid() is None


def test_start_launches_a_process_and_reports_its_pid():
    manager = make_manager()

    pid = manager.start()

    assert pid > 0
    assert manager.is_running() is True
    assert manager.pid() == pid

    manager.stop()


def test_start_twice_raises_already_running():
    manager = make_manager()
    manager.start()

    with pytest.raises(MonitorAlreadyRunningError):
        manager.start()

    manager.stop()


def test_stop_without_start_raises_not_running():
    manager = make_manager()

    with pytest.raises(MonitorNotRunningError):
        manager.stop()


def test_stop_gracefully_terminates_the_process():
    manager = make_manager()
    manager.start()

    manager.stop()

    assert manager.is_running() is False
    assert manager.pid() is None


def test_stop_after_the_process_already_exited_raises_not_running():
    manager = MonitorProcessManager(command=[sys.executable, "-c", "pass"])
    manager.start()

    deadline = time.monotonic() + 5
    while manager.is_running() and time.monotonic() < deadline:
        time.sleep(0.05)

    assert manager.is_running() is False
    with pytest.raises(MonitorNotRunningError):
        manager.stop()
