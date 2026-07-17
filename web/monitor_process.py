"""Starts and stops the webcam monitor (``run.py``) as a child process.

This lets the dashboard offer a "Monitorar" / "Encerrar" button without the
monitor's own code (``app/``) knowing anything about the web layer.
"""

from __future__ import annotations

import logging
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUN_SCRIPT = PROJECT_ROOT / "run.py"
STOP_TIMEOUT_SECONDS = 10


class MonitorAlreadyRunningError(Exception):
    """Raised when trying to start the monitor while it is already running."""


class MonitorNotRunningError(Exception):
    """Raised when trying to stop the monitor while it is not running."""


class MonitorProcessManager:
    """Starts, stops and reports on a single monitor subprocess.

    Only tracks processes it started itself; it has no way to detect or
    manage a monitor instance launched outside the dashboard (e.g. directly
    via ``python run.py`` in another terminal).
    """

    def __init__(
        self,
        command: Optional[List[str]] = None,
        cwd: Optional[Path] = None,
    ) -> None:
        self._command = command or [sys.executable, str(RUN_SCRIPT)]
        self._cwd = cwd or PROJECT_ROOT
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def is_running(self) -> bool:
        with self._lock:
            return self._is_running_locked()

    def pid(self) -> Optional[int]:
        with self._lock:
            return self._process.pid if self._is_running_locked() else None

    def _is_running_locked(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self) -> int:
        """Launch the monitor process.

        Raises:
            MonitorAlreadyRunningError: If a monitor process started by this
                manager is already running.
        """
        with self._lock:
            if self._is_running_locked():
                raise MonitorAlreadyRunningError("The monitor is already running.")

            self._process = subprocess.Popen(self._command, cwd=self._cwd)
            logger.info("Monitor process started (pid=%s)", self._process.pid)
            return self._process.pid

    def stop(self) -> None:
        """Stop the running monitor process gracefully.

        Sends SIGINT first (equivalent to Ctrl+C), which ``app/main.py``
        already handles to release the camera and close windows cleanly.
        Escalates to SIGTERM and then SIGKILL only if the process does not
        exit in time.

        Raises:
            MonitorNotRunningError: If no monitor process started by this
                manager is currently running.
        """
        with self._lock:
            if not self._is_running_locked():
                raise MonitorNotRunningError("The monitor is not running.")
            process = self._process

        process.send_signal(signal.SIGINT)
        if not self._wait(process, STOP_TIMEOUT_SECONDS):
            logger.warning("Monitor did not stop after SIGINT, terminating it.")
            process.terminate()
            if not self._wait(process, STOP_TIMEOUT_SECONDS):
                logger.warning("Monitor did not terminate, killing it.")
                process.kill()
                process.wait()

        logger.info("Monitor process stopped (pid=%s)", process.pid)

    @staticmethod
    def _wait(process: subprocess.Popen, timeout: float) -> bool:
        try:
            process.wait(timeout=timeout)
            return True
        except subprocess.TimeoutExpired:
            return False
