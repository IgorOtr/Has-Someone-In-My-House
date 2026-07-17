"""Tests for the /ws/webcam WebSocket endpoint.

No real model, no real MySQL: the detector/image manager/alert recorder are
fakes, and get_db/get_auth_settings are already overridden by the shared
autouse fixture in tests/web/conftest.py (in-memory SQLite).
"""

from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import load_config
from app.models import Detection
from tests.web.conftest import TEST_AUTH_SETTINGS
from web.auth_service import register_user
from web.dependencies import (
    get_alert_recorder,
    get_image_manager,
    get_person_detector,
    get_settings,
)
from web.security import create_access_token
from web.server import app


class FakeDetector:
    def __init__(self, always_detect: bool = True):
        self.always_detect = always_detect

    def detect(self, frame):
        if not self.always_detect:
            return []
        return [Detection(x1=0, y1=0, x2=5, y2=5, confidence=0.9, class_id=0, class_name="person")]


class FakeImageManager:
    def __init__(self):
        self.calls = []

    def save_detection_image(self, frame, detections):
        self.calls.append(detections)
        return Path("detections/fake.jpg")


class FakeAlertRecorder:
    def __init__(self):
        self.calls = []

    def record_alert(self, message, image_path):
        self.calls.append((message, image_path))
        return True


def make_jpeg_bytes() -> bytes:
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    success, encoded = cv2.imencode(".jpg", frame)
    assert success
    return encoded.tobytes()


def make_token(db_session_factory) -> str:
    session = db_session_factory()
    try:
        user = register_user(session, "webcam@example.com", "supersecret", "5524981402661")
    finally:
        session.close()
    return create_access_token(
        user.email, TEST_AUTH_SETTINGS.jwt_secret_key, TEST_AUTH_SETTINGS.jwt_expires_minutes
    )


@pytest.fixture
def fakes():
    image_manager = FakeImageManager()
    alert_recorder = FakeAlertRecorder()
    app.dependency_overrides[get_settings] = lambda: load_config(
        env={
            "DETECTION_WINDOW_SIZE": "1",
            "MINIMUM_POSITIVE_FRAMES": "1",
            "CAPTURE_COOLDOWN_SECONDS": "0",
            "CAPTURE_DELAY_SECONDS": "0",
        }
    )
    app.dependency_overrides[get_person_detector] = lambda: FakeDetector(always_detect=True)
    app.dependency_overrides[get_image_manager] = lambda: image_manager
    app.dependency_overrides[get_alert_recorder] = lambda: alert_recorder
    yield image_manager, alert_recorder
    app.dependency_overrides.pop(get_settings, None)
    app.dependency_overrides.pop(get_person_detector, None)
    app.dependency_overrides.pop(get_image_manager, None)
    app.dependency_overrides.pop(get_alert_recorder, None)


def test_rejects_missing_token(fakes):
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/webcam") as ws:
            ws.send_json({})
            ws.receive_json()


def test_rejects_invalid_token(fakes):
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/webcam") as ws:
            ws.send_json({"token": "not-a-real-token"})
            ws.receive_json()


def test_processes_frame_and_confirms_detection(fakes, db_session_factory):
    image_manager, alert_recorder = fakes
    token = make_token(db_session_factory)
    client = TestClient(app)

    with client.websocket_connect("/ws/webcam") as ws:
        ws.send_json({"token": token})
        ws.send_bytes(make_jpeg_bytes())
        payload = ws.receive_json()

    assert payload["status"] == "Image saved"
    assert payload["person_count"] == 1
    assert len(image_manager.calls) == 1
    assert len(alert_recorder.calls) == 1


def test_does_not_confirm_when_no_person_detected(fakes, db_session_factory):
    image_manager, alert_recorder = fakes
    app.dependency_overrides[get_person_detector] = lambda: FakeDetector(always_detect=False)
    token = make_token(db_session_factory)
    client = TestClient(app)

    with client.websocket_connect("/ws/webcam") as ws:
        ws.send_json({"token": token})
        ws.send_bytes(make_jpeg_bytes())
        payload = ws.receive_json()

    assert payload["status"] == "Monitoring"
    assert payload["person_count"] == 0
    assert len(image_manager.calls) == 0
    assert len(alert_recorder.calls) == 0
