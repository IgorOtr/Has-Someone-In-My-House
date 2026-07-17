"""Tests for web.alert_service using an in-memory SQLite session (no MySQL)."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from web import db_models  # noqa: F401  (registers AlertModel on Base.metadata)
from web.alert_service import create_alert, list_alerts
from web.db import Base


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def test_create_alert_persists_message_and_image_path(db_session):
    alert = create_alert(db_session, "Pessoa detectada", "detections/detection_1.jpg")

    assert alert.id is not None
    assert alert.message == "Pessoa detectada"
    assert alert.image_path == "detections/detection_1.jpg"


def test_create_alert_defaults_to_not_sent(db_session):
    alert = create_alert(db_session, "Pessoa detectada", "detections/detection_1.jpg")

    assert alert.sent is False


def test_create_alert_sets_created_at(db_session):
    alert = create_alert(db_session, "Pessoa detectada", "detections/detection_1.jpg")

    assert alert.created_at is not None


def test_create_alert_accepts_a_path_object(db_session):
    alert = create_alert(
        db_session, "Pessoa detectada", Path("detections") / "detection_1.jpg"
    )

    assert alert.image_path == str(Path("detections") / "detection_1.jpg")


def test_create_alert_allows_multiple_alerts(db_session):
    first = create_alert(db_session, "Pessoa detectada", "detections/first.jpg")
    second = create_alert(db_session, "Pessoa detectada novamente", "detections/second.jpg")

    assert first.id != second.id


def test_list_alerts_returns_most_recent_first(db_session):
    first = create_alert(db_session, "Primeiro alerta", "detections/first.jpg")
    second = create_alert(db_session, "Segundo alerta", "detections/second.jpg")
    third = create_alert(db_session, "Terceiro alerta", "detections/third.jpg")

    alerts = list_alerts(db_session)

    assert [alert.id for alert in alerts] == [third.id, second.id, first.id]


def test_list_alerts_returns_empty_list_when_there_are_none(db_session):
    assert list_alerts(db_session) == []


def test_list_alerts_respects_limit(db_session):
    for i in range(5):
        create_alert(db_session, f"Alerta {i}", f"detections/{i}.jpg")

    alerts = list_alerts(db_session, limit=2)

    assert len(alerts) == 2


def test_list_alerts_respects_offset(db_session):
    created = [create_alert(db_session, f"Alerta {i}", f"detections/{i}.jpg") for i in range(5)]
    expected_ids_newest_first = [alert.id for alert in reversed(created)]

    page = list_alerts(db_session, limit=2, offset=2)

    assert [alert.id for alert in page] == expected_ids_newest_first[2:4]
