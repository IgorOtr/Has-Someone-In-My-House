"""Sliding-window confirmation of person presence across frames.

This module has no dependency on OpenCV, NumPy or YOLO so it can be tested
in isolation and reused with any boolean presence signal.
"""

from __future__ import annotations

from collections import deque


class DetectionTracker:
    """Confirms detections only after enough positive frames in a window."""

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
        """Record whether the latest processed frame contained a person."""
        self._history.append(person_present)

    def is_confirmed(self) -> bool:
        """Return True when enough recent frames contained a person."""
        return sum(self._history) >= self._minimum_positive_frames

    def reset(self) -> None:
        """Clear the tracking history."""
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
