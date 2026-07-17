"""Tests for app.alert_recorder.

None of these tests touch a real MySQL server or send a real WhatsApp
message: record_alert is exercised against an in-memory SQLite session
factory, WhatsApp sending is monkeypatched, and create()'s failure paths
are exercised by monkeypatching its setup calls.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.alert_recorder as alert_recorder_module
from app.alert_recorder import AlertRecorder
from web import db_models  # noqa: F401  (registers models on Base.metadata)
from web.auth_service import register_user
from web.db import Base
from web.db_models import AlertModel
from web.whatsapp_client import WhatsAppSendError


@pytest.fixture
def sqlite_session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


def get_alert(session_factory) -> AlertModel:
    session = session_factory()
    try:
        return session.query(AlertModel).one()
    finally:
        session.close()


def test_record_alert_persists_a_row(sqlite_session_factory):
    recorder = AlertRecorder(session_factory=sqlite_session_factory)

    success = recorder.record_alert("Pessoa detectada", Path("detections/detection_1.jpg"))

    assert success is True
    alert = get_alert(sqlite_session_factory)
    assert alert.message == "Pessoa detectada"
    assert alert.image_path == "detections/detection_1.jpg"


def test_record_alert_returns_false_without_a_session_factory():
    recorder = AlertRecorder(session_factory=None)

    success = recorder.record_alert("Pessoa detectada", Path("detections/detection_1.jpg"))

    assert success is False


def test_record_alert_returns_false_on_database_error(sqlite_session_factory):
    def broken_session_factory():
        raise RuntimeError("connection refused")

    recorder = AlertRecorder(session_factory=broken_session_factory)

    success = recorder.record_alert("Pessoa detectada", Path("detections/detection_1.jpg"))

    assert success is False


def test_record_alert_does_not_send_whatsapp_without_config(sqlite_session_factory, monkeypatch):
    called = []
    monkeypatch.setattr(
        alert_recorder_module, "send_whatsapp_image", lambda *a, **k: called.append(1)
    )
    recorder = AlertRecorder(session_factory=sqlite_session_factory, whatsapp_config=None)

    recorder.record_alert("Pessoa detectada", Path("detections/detection_1.jpg"))

    assert called == []
    assert get_alert(sqlite_session_factory).sent is False


def test_record_alert_skips_whatsapp_when_no_user_has_a_phone_number(
    sqlite_session_factory, monkeypatch
):
    called = []
    monkeypatch.setattr(
        alert_recorder_module, "send_whatsapp_image", lambda *a, **k: called.append(1)
    )
    recorder = AlertRecorder(
        session_factory=sqlite_session_factory, whatsapp_config=object()
    )

    recorder.record_alert("Pessoa detectada", Path("detections/detection_1.jpg"))

    assert called == []
    assert get_alert(sqlite_session_factory).sent is False


def test_record_alert_sends_whatsapp_and_marks_sent_on_success(
    sqlite_session_factory, monkeypatch
):
    session = sqlite_session_factory()
    register_user(session, "owner@example.com", "supersecret", "5524981402661")
    session.close()

    sent_calls = []
    monkeypatch.setattr(
        alert_recorder_module,
        "send_whatsapp_image",
        lambda config, phone, image_path, message: sent_calls.append((phone, image_path, message)),
    )
    recorder = AlertRecorder(session_factory=sqlite_session_factory, whatsapp_config=object())

    success = recorder.record_alert("Pessoa detectada", Path("detections/detection_1.jpg"))

    assert success is True
    assert sent_calls == [
        ("5524981402661", Path("detections/detection_1.jpg"), "Pessoa detectada")
    ]
    assert get_alert(sqlite_session_factory).sent is True


def test_record_alert_leaves_pending_when_whatsapp_send_fails(
    sqlite_session_factory, monkeypatch
):
    session = sqlite_session_factory()
    register_user(session, "owner@example.com", "supersecret", "5524981402661")
    session.close()

    def raise_send_error(config, phone, image_path, message):
        raise WhatsAppSendError("Z-API returned status 500")

    monkeypatch.setattr(alert_recorder_module, "send_whatsapp_image", raise_send_error)
    recorder = AlertRecorder(session_factory=sqlite_session_factory, whatsapp_config=object())

    success = recorder.record_alert("Pessoa detectada", Path("detections/detection_1.jpg"))

    assert success is True  # the alert was still persisted
    assert get_alert(sqlite_session_factory).sent is False


def test_create_disables_recording_when_database_setup_fails(monkeypatch):
    def raise_error(*_args, **_kwargs):
        raise RuntimeError("could not connect to MySQL")

    monkeypatch.setattr(alert_recorder_module, "load_auth_config", raise_error)

    recorder = AlertRecorder.create()

    assert recorder.record_alert("Pessoa detectada", Path("detections/detection_1.jpg")) is False


def test_create_builds_a_working_recorder_when_database_setup_succeeds(
    monkeypatch, sqlite_session_factory
):
    monkeypatch.setattr(
        alert_recorder_module,
        "load_auth_config",
        lambda: SimpleNamespace(database_url="sqlite:///unused"),
    )
    monkeypatch.setattr(alert_recorder_module, "ensure_database_exists", lambda _settings: None)
    monkeypatch.setattr(alert_recorder_module, "build_engine", lambda _url: object())
    monkeypatch.setattr(alert_recorder_module, "init_models", lambda _engine: None)
    monkeypatch.setattr(alert_recorder_module, "ensure_schema_migrations", lambda _engine: None)
    monkeypatch.setattr(
        alert_recorder_module, "build_session_factory", lambda _engine: sqlite_session_factory
    )
    monkeypatch.setattr(
        alert_recorder_module,
        "load_whatsapp_config",
        lambda: (_ for _ in ()).throw(RuntimeError("no Z-API config in this test")),
    )

    recorder = AlertRecorder.create()

    assert recorder.record_alert("Pessoa detectada", Path("detections/detection_1.jpg")) is True


def test_create_disables_whatsapp_but_keeps_alert_history_when_zapi_config_missing(
    monkeypatch, sqlite_session_factory
):
    monkeypatch.setattr(
        alert_recorder_module,
        "load_auth_config",
        lambda: SimpleNamespace(database_url="sqlite:///unused"),
    )
    monkeypatch.setattr(alert_recorder_module, "ensure_database_exists", lambda _settings: None)
    monkeypatch.setattr(alert_recorder_module, "build_engine", lambda _url: object())
    monkeypatch.setattr(alert_recorder_module, "init_models", lambda _engine: None)
    monkeypatch.setattr(alert_recorder_module, "ensure_schema_migrations", lambda _engine: None)
    monkeypatch.setattr(
        alert_recorder_module, "build_session_factory", lambda _engine: sqlite_session_factory
    )
    monkeypatch.setattr(
        alert_recorder_module,
        "load_whatsapp_config",
        lambda: (_ for _ in ()).throw(RuntimeError("missing ZAPI_CLIENT_TOKEN")),
    )

    recorder = AlertRecorder.create()

    assert recorder._whatsapp_config is None
    assert recorder.record_alert("Pessoa detectada", Path("detections/detection_1.jpg")) is True
    assert get_alert(sqlite_session_factory).sent is False
