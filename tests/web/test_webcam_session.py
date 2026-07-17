"""Tests for web.webcam_session.WebcamMonitorSession.

No real model, WebSocket or MySQL involved: the detector, image manager and
alert recorder are all fakes/mocks injected directly.
"""

from pathlib import Path

import numpy as np

from app.detector import InferenceError
from app.models import Detection
from web.webcam_session import (
    STATUS_COOLDOWN,
    STATUS_DETECTION_CONFIRMED,
    STATUS_IMAGE_SAVED,
    STATUS_INFERENCE_ERROR,
    STATUS_MONITORING,
    STATUS_PERSON_DETECTED,
    STATUS_SAVE_ERROR,
    WebcamMonitorSession,
)


def make_detection(confidence: float = 0.9) -> Detection:
    return Detection(x1=0, y1=0, x2=10, y2=10, confidence=confidence, class_id=0, class_name="person")


def make_frame() -> np.ndarray:
    return np.zeros((10, 10, 3), dtype=np.uint8)


class FakeDetector:
    def __init__(self, sequence):
        self._sequence = list(sequence)

    def detect(self, frame):
        value = self._sequence.pop(0) if self._sequence else []
        if isinstance(value, Exception):
            raise value
        return value


class FakeImageManager:
    def __init__(self, saved_path=Path("detections/fake.jpg")):
        self.calls = []
        self._saved_path = saved_path

    def save_detection_image(self, frame, detections):
        self.calls.append((frame, detections))
        return self._saved_path


class FailingImageManager:
    def save_detection_image(self, frame, detections):
        return None


class FakeAlertRecorder:
    def __init__(self):
        self.calls = []

    def record_alert(self, message, image_path):
        self.calls.append((message, image_path))
        return True


def make_session(detector, image_manager=None, alert_recorder=None, **overrides):
    defaults = dict(
        window_size=5,
        minimum_positive_frames=3,
        cooldown_seconds=0,
        capture_delay_seconds=0,
    )
    defaults.update(overrides)
    return WebcamMonitorSession(
        detector=detector,
        image_manager=image_manager or FakeImageManager(),
        alert_recorder=alert_recorder or FakeAlertRecorder(),
        **defaults,
    )


def test_status_monitoring_when_no_person():
    session = make_session(FakeDetector([[]]))

    payload = session.process_frame(make_frame())

    assert payload["status"] == STATUS_MONITORING
    assert payload["person_count"] == 0


def test_status_person_detected_before_confirmation():
    session = make_session(FakeDetector([[make_detection()]]))

    payload = session.process_frame(make_frame())

    assert payload["status"] == STATUS_PERSON_DETECTED
    assert payload["person_count"] == 1


def test_confirms_and_saves_after_enough_positive_frames():
    image_manager = FakeImageManager()
    alert_recorder = FakeAlertRecorder()
    detector = FakeDetector([[make_detection()], [make_detection()], [make_detection()]])
    session = make_session(
        detector,
        image_manager=image_manager,
        alert_recorder=alert_recorder,
        window_size=3,
        minimum_positive_frames=3,
    )

    payloads = [session.process_frame(make_frame()) for _ in range(3)]

    assert payloads[-1]["status"] == STATUS_IMAGE_SAVED
    assert len(image_manager.calls) == 1
    assert len(alert_recorder.calls) == 1


def test_does_not_save_again_during_cooldown():
    image_manager = FakeImageManager()
    detector = FakeDetector([[make_detection()]] * 2)
    session = make_session(
        detector,
        image_manager=image_manager,
        window_size=1,
        minimum_positive_frames=1,
        cooldown_seconds=60,
    )

    first = session.process_frame(make_frame())
    second = session.process_frame(make_frame())

    assert first["status"] == STATUS_IMAGE_SAVED
    assert second["status"] == STATUS_COOLDOWN
    assert len(image_manager.calls) == 1


def test_waits_for_capture_delay_before_saving():
    image_manager = FakeImageManager()
    session = make_session(
        FakeDetector([[make_detection()]]),
        image_manager=image_manager,
        window_size=1,
        minimum_positive_frames=1,
        capture_delay_seconds=999,  # nunca vence dentro do teste
    )

    payload = session.process_frame(make_frame())

    assert payload["status"] == STATUS_DETECTION_CONFIRMED
    assert len(image_manager.calls) == 0


def test_save_error_status_when_image_manager_fails():
    session = make_session(
        FakeDetector([[make_detection()]]),
        image_manager=FailingImageManager(),
        window_size=1,
        minimum_positive_frames=1,
    )

    payload = session.process_frame(make_frame())

    assert payload["status"] == STATUS_SAVE_ERROR


def test_inference_error_status():
    session = make_session(FakeDetector([InferenceError("boom")]))

    payload = session.process_frame(make_frame())

    assert payload["status"] == STATUS_INFERENCE_ERROR
    assert payload["person_count"] == 0
