"""Controle de cooldown: decide quando uma nova imagem de detecção pode ser salva."""

from __future__ import annotations

import time
from typing import Callable, Optional

ClockFn = Callable[[], float]


class CaptureController:
    """Decide se uma nova captura é permitida, aplicando cooldown e um
    atraso pós-confirmação (capture delay).

    O cooldown só começa depois que :meth:`notify_saved` é chamado, o que
    deve acontecer estritamente após a imagem ter sido salva com sucesso.

    Uma captura não é feita no instante em que a detecção é confirmada:
    quem chama deve primeiro reportar a confirmação via
    :meth:`notify_detection_confirmed`, e :meth:`is_capture_due` só retorna
    verdadeiro depois que ``capture_delay_seconds`` tiver passado desde
    essa confirmação (e o cooldown, se houver, também permitir).
    """

    def __init__(
        self,
        cooldown_seconds: float,
        capture_delay_seconds: float = 0.0,
        clock: ClockFn = time.monotonic,
    ) -> None:
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds cannot be negative.")
        if capture_delay_seconds < 0:
            raise ValueError("capture_delay_seconds cannot be negative.")
        self._cooldown_seconds = cooldown_seconds
        self._capture_delay_seconds = capture_delay_seconds
        self._clock = clock
        self._last_capture_time: Optional[float] = None
        self._pending_since: Optional[float] = None

    def can_capture(self) -> bool:
        """Retorna True quando o período de cooldown já passou."""
        if self._last_capture_time is None:
            return True
        return (self._clock() - self._last_capture_time) >= self._cooldown_seconds

    def notify_detection_confirmed(self) -> None:
        """Marca o início de um episódio de detecção confirmada.

        Idempotente: chamadas repetidas enquanto o mesmo episódio segue
        confirmado mantêm o timestamp original, então o atraso é medido a
        partir da primeira confirmação, não da última chamada.
        """
        if self._pending_since is None:
            self._pending_since = self._clock()

    def cancel_pending_capture(self) -> None:
        """Descarta uma captura pendente, ex.: quando a pessoa sai do
        quadro antes do atraso de captura terminar."""
        self._pending_since = None

    def is_capture_due(self) -> bool:
        """Retorna True quando o atraso de captura já passou e o cooldown permite."""
        if self._pending_since is None:
            return False
        if (self._clock() - self._pending_since) < self._capture_delay_seconds:
            return False
        return self.can_capture()

    def notify_saved(self) -> None:
        """Registra que uma imagem acabou de ser salva com sucesso, iniciando o cooldown."""
        self._last_capture_time = self._clock()
        self._pending_since = None

    def cooldown_remaining_seconds(self) -> float:
        """Retorna o tempo restante de cooldown, ou 0 se não estiver em cooldown."""
        if self._last_capture_time is None:
            return 0.0
        remaining = self._cooldown_seconds - (self._clock() - self._last_capture_time)
        return max(0.0, remaining)

    def reset(self) -> None:
        """Limpa o estado de cooldown e de captura pendente."""
        self._last_capture_time = None
        self._pending_since = None
