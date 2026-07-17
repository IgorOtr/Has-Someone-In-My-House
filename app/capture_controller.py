"""Cooldown management deciding when a new detection image may be saved."""

from __future__ import annotations

import time
from typing import Callable, Optional

ClockFn = Callable[[], float]


class CaptureController:
    """Decides whether a new capture is allowed, enforcing a cooldown and a
    post-confirmation capture delay.

    The cooldown only starts after :meth:`notify_saved` is called, which
    must happen strictly after the image has been persisted successfully.

    A capture is not taken the instant a detection is confirmed: callers
    must first report the confirmation via
    :meth:`notify_detection_confirmed`, and :meth:`is_capture_due` only
    turns true once ``capture_delay_seconds`` have elapsed since that
    confirmation (and the cooldown, if any, also allows it).
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
        """Return True when the cooldown period has elapsed."""
        if self._last_capture_time is None:
            return True
        return (self._clock() - self._last_capture_time) >= self._cooldown_seconds

    def notify_detection_confirmed(self) -> None:
        """Mark the start of a confirmed detection episode.

        Idempotent: calling this repeatedly while the same episode is still
        confirmed keeps the original timestamp, so the delay is measured
        from the first confirmation, not the last call.
        """
        if self._pending_since is None:
            self._pending_since = self._clock()

    def cancel_pending_capture(self) -> None:
        """Discard a pending capture, e.g. when the person leaves the frame
        before the capture delay elapses."""
        self._pending_since = None

    def is_capture_due(self) -> bool:
        """Return True once the capture delay has elapsed and the cooldown allows it."""
        if self._pending_since is None:
            return False
        if (self._clock() - self._pending_since) < self._capture_delay_seconds:
            return False
        return self.can_capture()

    def notify_saved(self) -> None:
        """Record that an image was just saved successfully, starting the cooldown."""
        self._last_capture_time = self._clock()
        self._pending_since = None

    def cooldown_remaining_seconds(self) -> float:
        """Return the remaining cooldown time, or 0 when not in cooldown."""
        if self._last_capture_time is None:
            return 0.0
        remaining = self._cooldown_seconds - (self._clock() - self._last_capture_time)
        return max(0.0, remaining)

    def reset(self) -> None:
        """Clear the cooldown and pending-capture state."""
        self._last_capture_time = None
        self._pending_since = None
