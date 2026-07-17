"""Inicia e para o monitor da webcam (``run.py``) como um processo filho.

Isso permite que o dashboard ofereça um botão "Monitorar" / "Encerrar" sem
que o código do monitor (``app/``) precise saber nada sobre a camada web.
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
    """Levantada ao tentar iniciar o monitor quando ele já está rodando."""


class MonitorNotRunningError(Exception):
    """Levantada ao tentar parar o monitor quando ele não está rodando."""


class MonitorProcessManager:
    """Inicia, para e informa o estado de um único subprocesso do monitor.

    Só rastreia processos que ele mesmo iniciou; não tem como detectar ou
    gerenciar uma instância do monitor iniciada fora do dashboard (ex.:
    diretamente via ``python run.py`` em outro terminal).
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
        """Inicia o processo do monitor.

        Raises:
            MonitorAlreadyRunningError: Se um processo do monitor iniciado
                por este manager já estiver rodando.
        """
        with self._lock:
            if self._is_running_locked():
                raise MonitorAlreadyRunningError("The monitor is already running.")

            self._process = subprocess.Popen(self._command, cwd=self._cwd)
            logger.info("Monitor process started (pid=%s)", self._process.pid)
            return self._process.pid

    def stop(self) -> None:
        """Para o processo do monitor em execução, de forma graciosa.

        Envia SIGINT primeiro (equivalente a Ctrl+C), que o
        ``app/main.py`` já trata para liberar a câmera e fechar as janelas
        corretamente. Escala para SIGTERM e depois SIGKILL só se o
        processo não sair a tempo.

        Raises:
            MonitorNotRunningError: Se nenhum processo do monitor iniciado
                por este manager estiver rodando no momento.
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
