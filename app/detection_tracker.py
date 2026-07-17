"""Confirmação por janela deslizante da presença de pessoas entre frames.

Este módulo não depende de OpenCV, NumPy ou YOLO, então pode ser testado
isoladamente e reutilizado com qualquer sinal booleano de presença.
"""

from __future__ import annotations

from collections import deque


class DetectionTracker:
    """Só confirma a detecção após frames positivos suficientes na janela."""

    def __init__(self, window_size: int, minimum_positive_frames: int) -> None:
        if window_size <= 0:
            raise ValueError("window_size must be greater than 0.")
        if minimum_positive_frames <= 0:
            raise ValueError("minimum_positive_frames must be greater than 0.")
        if minimum_positive_frames > window_size:
            raise ValueError(
                "minimum_positive_frames cannot be greater than window_size."
            )

        self._window_size = window_size
        self._minimum_positive_frames = minimum_positive_frames
        self._history: deque[bool] = deque(maxlen=window_size)

    def update(self, person_present: bool) -> None:
        """Registra se o último frame processado continha uma pessoa."""
        self._history.append(person_present)

    def is_confirmed(self) -> bool:
        """Retorna True quando frames recentes suficientes continham uma pessoa."""
        return sum(self._history) >= self._minimum_positive_frames

    def reset(self) -> None:
        """Limpa o histórico de rastreamento."""
        self._history.clear()

    @property
    def positive_count(self) -> int:
        return sum(self._history)

    @property
    def window_size(self) -> int:
        return self._window_size

    @property
    def minimum_positive_frames(self) -> int:
        return self._minimum_positive_frames
