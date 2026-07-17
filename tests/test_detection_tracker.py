"""Tests for app.detection_tracker: pure logic, no external dependencies."""

import pytest

from app.detection_tracker import DetectionTracker


def test_not_confirmed_without_enough_results():
    tracker = DetectionTracker(window_size=5, minimum_positive_frames=3)

    tracker.update(True)
    tracker.update(True)

    assert tracker.is_confirmed() is False


def test_not_confirmed_with_fewer_positive_frames_than_required():
    tracker = DetectionTracker(window_size=5, minimum_positive_frames=3)

    for value in [True, True, False, False, False]:
        tracker.update(value)

    assert tracker.is_confirmed() is False


def test_confirmed_with_three_of_five_positive_frames():
    tracker = DetectionTracker(window_size=5, minimum_positive_frames=3)

    for value in [True, False, True, False, True]:
        tracker.update(value)

    assert tracker.is_confirmed() is True


def test_oldest_values_are_dropped_from_the_window():
    tracker = DetectionTracker(window_size=3, minimum_positive_frames=2)

    tracker.update(True)
    tracker.update(True)
    assert tracker.is_confirmed() is True

    # Two False pushes the two True values out of the window.
    tracker.update(False)
    tracker.update(False)

    assert tracker.is_confirmed() is False


def test_reset_clears_history():
    tracker = DetectionTracker(window_size=5, minimum_positive_frames=3)

    for _ in range(5):
        tracker.update(True)
    assert tracker.is_confirmed() is True

    tracker.reset()

    assert tracker.is_confirmed() is False
    assert tracker.positive_count == 0


def test_accepts_configurable_window_and_threshold():
    tracker = DetectionTracker(window_size=10, minimum_positive_frames=1)

    tracker.update(True)

    assert tracker.window_size == 10
    assert tracker.minimum_positive_frames == 1
    assert tracker.is_confirmed() is True


@pytest.mark.parametrize(
    "window_size, minimum_positive_frames",
    [
        (0, 1),
        (-1, 1),
        (5, 0),
        (5, -1),
        (3, 4),
    ],
)
def test_rejects_invalid_configuration(window_size, minimum_positive_frames):
    with pytest.raises(ValueError):
        DetectionTracker(window_size=window_size, minimum_positive_frames=minimum_positive_frames)
