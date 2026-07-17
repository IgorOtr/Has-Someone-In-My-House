"""Tests for app.alert_recorder.

None of these tests touch a real MySQL server: record_alert is exercised
against an in-memory SQLite session factory, and create()'s failure path is
exercised by monkeypatching its database setup calls.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.alert_recorder as alert_recorder_module
from app.alert_recorder import AlertRecorder
from web import db_models  # noqa: F401  (registers AlertModel on Base.metadata)
from web.db import Base
from web.db_models import AlertModel


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


def test_record_alert_persists_a_row(sqlite_session_factory):
    recorder = AlertRecorder(session_factory=sqlite_session_factory)

    success = recorder.record_alert("Pessoa detectada", Path("detections/detection_1.jpg"))

    assert success is True
    session = sqlite_session_factory()
    try:
        rows = session.query(AlertModel).all()
    finally:
        session.close()
    assert len(rows) == 1
    assert rows[0].message == "Pessoa detectada"
    assert rows[0].image_path == "detections/detection_1.jpg"


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
    monkeypatch.setattr(
        alert_recorder_module, "build_session_factory", lambda _engine: sqlite_session_factory
    )

    recorder = AlertRecorder.create()

    assert recorder.record_alert("Pessoa detectada", Path("detections/detection_1.jpg")) is True
