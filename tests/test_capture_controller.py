"""Tests for app.capture_controller using a fake, injectable clock."""

import pytest

from app.capture_controller import CaptureController


class FakeClock:
    """A controllable clock, avoiding real ``sleep`` calls in tests."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def advance(self, seconds: float) -> None:
        self._now += seconds

    def __call__(self) -> float:
        return self._now


def test_allows_first_capture():
    controller = CaptureController(cooldown_seconds=60, clock=FakeClock())

    assert controller.can_capture() is True


def test_blocks_capture_during_cooldown():
    clock = FakeClock()
    controller = CaptureController(cooldown_seconds=60, clock=clock)

    controller.notify_saved()
    clock.advance(30)

    assert controller.can_capture() is False


def test_allows_capture_again_after_cooldown_elapses():
    clock = FakeClock()
    controller = CaptureController(cooldown_seconds=60, clock=clock)

    controller.notify_saved()
    clock.advance(60)

    assert controller.can_capture() is True


def test_cooldown_does_not_start_before_saving():
    clock = FakeClock()
    controller = CaptureController(cooldown_seconds=60, clock=clock)

    clock.advance(1000)

    assert controller.can_capture() is True


def test_cooldown_does_not_start_when_save_fails():
    clock = FakeClock()
    controller = CaptureController(cooldown_seconds=60, clock=clock)

    # Simulate a failed save: notify_saved is simply never called.
    assert controller.can_capture() is True
    clock.advance(5)
    assert controller.can_capture() is True


def test_cooldown_starts_after_successful_save():
    clock = FakeClock()
    controller = CaptureController(cooldown_seconds=60, clock=clock)

    controller.notify_saved()

    assert controller.can_capture() is False
    assert controller.cooldown_remaining_seconds() == pytest.approx(60)


def test_reset_clears_cooldown_state():
    clock = FakeClock()
    controller = CaptureController(cooldown_seconds=60, clock=clock)

    controller.notify_saved()
    assert controller.can_capture() is False

    controller.reset()

    assert controller.can_capture() is True
    assert controller.cooldown_remaining_seconds() == 0.0


def test_rejects_negative_cooldown():
    with pytest.raises(ValueError):
        CaptureController(cooldown_seconds=-1, clock=FakeClock())


def test_rejects_negative_capture_delay():
    with pytest.raises(ValueError):
        CaptureController(cooldown_seconds=0, capture_delay_seconds=-1, clock=FakeClock())


def test_capture_not_due_without_a_confirmed_detection():
    controller = CaptureController(cooldown_seconds=0, capture_delay_seconds=1, clock=FakeClock())

    assert controller.is_capture_due() is False


def test_capture_not_due_before_delay_elapses():
    clock = FakeClock()
    controller = CaptureController(cooldown_seconds=0, capture_delay_seconds=1, clock=clock)

    controller.notify_detection_confirmed()
    clock.advance(0.5)

    assert controller.is_capture_due() is False


def test_capture_due_after_delay_elapses():
    clock = FakeClock()
    controller = CaptureController(cooldown_seconds=0, capture_delay_seconds=1, clock=clock)

    controller.notify_detection_confirmed()
    clock.advance(1)

    assert controller.is_capture_due() is True


def test_delay_is_measured_from_first_confirmation_not_the_latest_call():
    clock = FakeClock()
    controller = CaptureController(cooldown_seconds=0, capture_delay_seconds=1, clock=clock)

    controller.notify_detection_confirmed()
    clock.advance(0.6)
    controller.notify_detection_confirmed()  # Should not push the deadline forward.
    clock.advance(0.5)

    assert controller.is_capture_due() is True


def test_cancel_pending_capture_resets_the_delay_timer():
    clock = FakeClock()
    controller = CaptureController(cooldown_seconds=0, capture_delay_seconds=1, clock=clock)

    controller.notify_detection_confirmed()
    clock.advance(0.9)
    controller.cancel_pending_capture()
    clock.advance(0.9)

    assert controller.is_capture_due() is False

    controller.notify_detection_confirmed()
    clock.advance(1.01)

    assert controller.is_capture_due() is True


def test_capture_due_still_respects_an_active_cooldown():
    clock = FakeClock()
    controller = CaptureController(cooldown_seconds=60, capture_delay_seconds=1, clock=clock)

    controller.notify_saved()
    controller.notify_detection_confirmed()
    clock.advance(1)

    assert controller.is_capture_due() is False


def test_notify_saved_clears_pending_capture():
    clock = FakeClock()
    controller = CaptureController(cooldown_seconds=0, capture_delay_seconds=1, clock=clock)

    controller.notify_detection_confirmed()
    clock.advance(1)
    controller.notify_saved()

    assert controller.is_capture_due() is False


def test_reset_clears_pending_capture():
    clock = FakeClock()
    controller = CaptureController(cooldown_seconds=0, capture_delay_seconds=1, clock=clock)

    controller.notify_detection_confirmed()
    clock.advance(1)
    controller.reset()

    assert controller.is_capture_due() is False
