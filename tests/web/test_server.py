"""Tests for the FastAPI dashboard using an in-memory TestClient.

No webcam, model or network access is involved: the image directory is a
pytest tmp_path, injected via a dependency override.
"""

import dataclasses
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import load_config
from tests.web.conftest import TEST_AUTH_SETTINGS
from web.alert_service import create_alert
from web.dependencies import get_auth_settings, get_current_user, get_monitor_manager, get_settings
from web.monitor_process import MonitorAlreadyRunningError, MonitorNotRunningError
from web.server import app


class FakeUser:
    """Stand-in for UserModel, used to bypass real JWT verification in tests
    that are not specifically about authentication."""

    def __init__(self, id: int = 1, email: str = "test@example.com") -> None:
        self.id = id
        self.email = email
        self.created_at = datetime(2026, 1, 1)


class FakeMonitorManager:
    """In-memory stand-in for MonitorProcessManager: no real subprocess."""

    def __init__(self) -> None:
        self._running = False
        self._pid = None

    def is_running(self) -> bool:
        return self._running

    def pid(self):
        return self._pid

    def start(self) -> int:
        if self._running:
            raise MonitorAlreadyRunningError("The monitor is already running.")
        self._running = True
        self._pid = 4242
        return self._pid

    def stop(self) -> None:
        if not self._running:
            raise MonitorNotRunningError("The monitor is not running.")
        self._running = False
        self._pid = None


def make_client(tmp_path: Path, monitor_manager=None, authenticated: bool = True) -> TestClient:
    test_settings = load_config(
        env={
            "IMAGE_DIRECTORY": str(tmp_path),
            "IMAGE_FORMAT": "jpg",
        }
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    if monitor_manager is not None:
        app.dependency_overrides[get_monitor_manager] = lambda: monitor_manager
    if authenticated:
        app.dependency_overrides[get_current_user] = lambda: FakeUser()
    client = TestClient(app)
    return client


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def touch(path: Path) -> None:
    path.write_bytes(b"fake-jpeg-content")


def test_status_reports_zero_detections_for_empty_directory(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert body["total_detections"] == 0
    assert body["latest_detection_at"] is None
    assert body["capture_delay_seconds"] == 0.5


def test_lists_detections_created_on_disk(tmp_path):
    touch(tmp_path / "detection_20260716_100000_000000.jpg")
    touch(tmp_path / "detection_20260716_120000_000000.jpg")
    client = make_client(tmp_path)

    response = client.get("/api/detections")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["filename"] == "detection_20260716_120000_000000.jpg"
    assert body[0]["image_url"] == "/api/detections/detection_20260716_120000_000000.jpg/image"


def test_get_detection_image_returns_the_file(tmp_path):
    touch(tmp_path / "detection_20260716_100000_000000.jpg")
    client = make_client(tmp_path)

    response = client.get("/api/detections/detection_20260716_100000_000000.jpg/image")

    assert response.status_code == 200
    assert response.content == b"fake-jpeg-content"


def test_get_detection_image_returns_404_for_missing_file(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/api/detections/missing.jpg/image")

    assert response.status_code == 404


def test_delete_detection_removes_file(tmp_path):
    touch(tmp_path / "detection_20260716_100000_000000.jpg")
    client = make_client(tmp_path)

    response = client.delete("/api/detections/detection_20260716_100000_000000.jpg")

    assert response.status_code == 204
    assert not (tmp_path / "detection_20260716_100000_000000.jpg").exists()


def test_delete_detection_returns_404_for_missing_file(tmp_path):
    client = make_client(tmp_path)

    response = client.delete("/api/detections/missing.jpg")

    assert response.status_code == 404


def test_status_reflects_latest_detection_timestamp(tmp_path):
    touch(tmp_path / "detection_20260716_100000_000000.jpg")
    touch(tmp_path / "detection_20260716_120000_000000.jpg")
    client = make_client(tmp_path)

    response = client.get("/api/status")

    body = response.json()
    assert body["total_detections"] == 2
    assert body["latest_detection_at"].startswith("2026-07-16T12:00:00")


def test_monitor_status_reports_not_running_by_default(tmp_path):
    client = make_client(tmp_path, monitor_manager=FakeMonitorManager())

    response = client.get("/api/monitor/status")

    assert response.status_code == 200
    assert response.json() == {"running": False, "pid": None}


def test_monitor_start_reports_running_and_pid(tmp_path):
    client = make_client(tmp_path, monitor_manager=FakeMonitorManager())

    response = client.post("/api/monitor/start")

    assert response.status_code == 200
    body = response.json()
    assert body["running"] is True
    assert body["pid"] == 4242


def test_monitor_start_twice_returns_409(tmp_path):
    client = make_client(tmp_path, monitor_manager=FakeMonitorManager())
    client.post("/api/monitor/start")

    response = client.post("/api/monitor/start")

    assert response.status_code == 409


def test_monitor_stop_reports_not_running(tmp_path):
    manager = FakeMonitorManager()
    manager.start()
    client = make_client(tmp_path, monitor_manager=manager)

    response = client.post("/api/monitor/stop")

    assert response.status_code == 200
    assert response.json() == {"running": False, "pid": None}


def test_monitor_stop_without_running_returns_409(tmp_path):
    client = make_client(tmp_path, monitor_manager=FakeMonitorManager())

    response = client.post("/api/monitor/stop")

    assert response.status_code == 409


def register(client: TestClient, email: str = "user@example.com", password: str = "supersecret"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def login(client: TestClient, email: str = "user@example.com", password: str = "supersecret"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_register_creates_a_user(tmp_path):
    client = make_client(tmp_path, authenticated=False)

    response = register(client)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "user@example.com"
    assert "id" in body
    assert "password" not in body


def test_register_rejects_duplicate_email(tmp_path):
    client = make_client(tmp_path, authenticated=False)
    register(client)

    response = register(client)

    assert response.status_code == 409


def test_register_rejects_short_password(tmp_path):
    client = make_client(tmp_path, authenticated=False)

    response = register(client, password="short")

    assert response.status_code == 422


def test_register_rejects_invalid_email(tmp_path):
    client = make_client(tmp_path, authenticated=False)

    response = register(client, email="not-an-email")

    assert response.status_code == 422


def test_login_returns_token_for_valid_credentials(tmp_path):
    client = make_client(tmp_path, authenticated=False)
    register(client)

    response = login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 0


def test_login_rejects_wrong_password(tmp_path):
    client = make_client(tmp_path, authenticated=False)
    register(client)

    response = login(client, password="wrong-password")

    assert response.status_code == 401


def test_login_rejects_unknown_email(tmp_path):
    client = make_client(tmp_path, authenticated=False)

    response = login(client)

    assert response.status_code == 401


def test_me_endpoint_returns_the_logged_in_user(tmp_path):
    client = make_client(tmp_path, authenticated=False)
    register(client)
    token = login(client).json()["access_token"]

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


def test_protected_endpoint_rejects_missing_token(tmp_path):
    client = make_client(tmp_path, authenticated=False)

    response = client.get("/api/status")

    assert response.status_code == 401


def test_protected_endpoint_rejects_invalid_token(tmp_path):
    client = make_client(tmp_path, authenticated=False)

    response = client.get("/api/status", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


def test_protected_endpoint_accepts_a_valid_token(tmp_path):
    client = make_client(tmp_path, authenticated=False)
    register(client)
    token = login(client).json()["access_token"]

    response = client.get("/api/status", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200


def test_monitor_endpoints_require_authentication(tmp_path):
    client = make_client(tmp_path, monitor_manager=FakeMonitorManager(), authenticated=False)

    assert client.get("/api/monitor/status").status_code == 401
    assert client.post("/api/monitor/start").status_code == 401
    assert client.post("/api/monitor/stop").status_code == 401


def test_detection_image_and_delete_require_authentication(tmp_path):
    touch(tmp_path / "detection_20260716_100000_000000.jpg")
    client = make_client(tmp_path, authenticated=False)

    assert client.get("/api/detections").status_code == 401
    assert client.get("/api/detections/detection_20260716_100000_000000.jpg/image").status_code == 401
    assert client.delete("/api/detections/detection_20260716_100000_000000.jpg").status_code == 401


def test_register_rejects_when_public_registration_disabled(tmp_path):
    client = make_client(tmp_path, authenticated=False)
    disabled_settings = dataclasses.replace(TEST_AUTH_SETTINGS, allow_public_registration=False)
    app.dependency_overrides[get_auth_settings] = lambda: disabled_settings

    response = register(client)

    assert response.status_code == 403


def test_login_is_rate_limited_after_repeated_attempts(tmp_path):
    client = make_client(tmp_path, authenticated=False)
    register(client)

    for _ in range(5):
        response = login(client, password="wrong-password")
        assert response.status_code == 401

    response = login(client, password="wrong-password")

    assert response.status_code == 429


def test_register_is_rate_limited_after_repeated_attempts(tmp_path):
    client = make_client(tmp_path, authenticated=False)

    for i in range(5):
        response = register(client, email=f"user{i}@example.com")
        assert response.status_code == 201

    response = register(client, email="user-over-limit@example.com")

    assert response.status_code == 429


def test_responses_include_basic_security_headers(tmp_path):
    client = make_client(tmp_path, authenticated=False)

    response = client.get("/api/status")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"


def make_alert(db_session_factory, message="Pessoa detectada", image_path="detections/detection_1.jpg"):
    session = db_session_factory()
    try:
        return create_alert(session, message, image_path)
    finally:
        session.close()


def test_list_alerts_requires_authentication(tmp_path):
    client = make_client(tmp_path, authenticated=False)

    assert client.get("/api/alerts").status_code == 401


def test_list_alerts_returns_empty_list_when_none_exist(tmp_path):
    client = make_client(tmp_path)

    response = client.get("/api/alerts")

    assert response.status_code == 200
    assert response.json() == []


def test_list_alerts_orders_most_recent_first(tmp_path, db_session_factory):
    make_alert(db_session_factory, message="Primeiro alerta")
    make_alert(db_session_factory, message="Segundo alerta")
    client = make_client(tmp_path)

    response = client.get("/api/alerts")

    body = response.json()
    assert [item["message"] for item in body] == ["Segundo alerta", "Primeiro alerta"]


def test_list_alerts_includes_image_url_and_sent_status(tmp_path, db_session_factory):
    make_alert(
        db_session_factory,
        message="Pessoa detectada",
        image_path="detections/detection_20260716_100000_000000.jpg",
    )
    client = make_client(tmp_path)

    response = client.get("/api/alerts")

    body = response.json()[0]
    assert body["image_url"] == "/api/detections/detection_20260716_100000_000000.jpg/image"
    assert body["sent"] is False


def test_list_alerts_respects_limit_and_offset(tmp_path, db_session_factory):
    for i in range(5):
        make_alert(db_session_factory, message=f"Alerta {i}", image_path=f"detections/{i}.jpg")
    client = make_client(tmp_path)

    response = client.get("/api/alerts?limit=2&offset=2")

    assert len(response.json()) == 2
