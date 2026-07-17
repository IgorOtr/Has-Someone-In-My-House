"""Tests for app.main._build_alert_message: pure formatting, no camera/model/DB."""

from app.main import _build_alert_message
from app.models import Detection


def make_detection(confidence: float) -> Detection:
    return Detection(x1=0, y1=0, x2=10, y2=10, confidence=confidence, class_id=0, class_name="person")


def test_message_for_single_person():
    message = _build_alert_message([make_detection(0.87)])

    assert "1 pessoa" in message
    assert "1 pessoas" not in message
    assert "87%" in message


def test_message_for_multiple_people_uses_plural():
    message = _build_alert_message([make_detection(0.6), make_detection(0.9)])

    assert "2 pessoas" in message


def test_message_uses_the_highest_confidence():
    message = _build_alert_message([make_detection(0.5), make_detection(0.95)])

    assert "95%" in message


def test_message_handles_no_detections_gracefully():
    message = _build_alert_message([])

    assert "0 pessoas" in message
    assert "0%" in message
