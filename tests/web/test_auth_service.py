"""Tests for web.auth_service using an in-memory SQLite session (no MySQL)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import web.auth_service as auth_service_module
from web import db_models  # noqa: F401  (registers UserModel on Base.metadata)
from web.auth_service import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    authenticate_user,
    get_notification_phone_number,
    register_user,
)
from web.db import Base
from web.db_models import UserModel


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


def test_register_user_creates_a_user_with_hashed_password(db_session):
    user = register_user(db_session, "user@example.com", "supersecret", "5524981402661")

    assert user.id is not None
    assert user.email == "user@example.com"
    assert user.hashed_password != "supersecret"


def test_register_user_stores_phone_number(db_session):
    user = register_user(db_session, "user@example.com", "supersecret", "5524981402661")

    assert user.phone_number == "5524981402661"


def test_register_user_normalizes_email_case_and_whitespace(db_session):
    user = register_user(db_session, "  User@Example.com  ", "supersecret", "5524981402661")

    assert user.email == "user@example.com"


def test_register_user_rejects_duplicate_email(db_session):
    register_user(db_session, "user@example.com", "supersecret", "5524981402661")

    with pytest.raises(EmailAlreadyRegisteredError):
        register_user(db_session, "user@example.com", "anotherpassword", "5524981402661")


def test_register_user_rejects_duplicate_email_case_insensitively(db_session):
    register_user(db_session, "user@example.com", "supersecret", "5524981402661")

    with pytest.raises(EmailAlreadyRegisteredError):
        register_user(db_session, "USER@EXAMPLE.COM", "anotherpassword", "5524981402661")


def test_authenticate_user_succeeds_with_correct_credentials(db_session):
    register_user(db_session, "user@example.com", "supersecret", "5524981402661")

    user = authenticate_user(db_session, "user@example.com", "supersecret")

    assert user.email == "user@example.com"


def test_authenticate_user_rejects_wrong_password(db_session):
    register_user(db_session, "user@example.com", "supersecret", "5524981402661")

    with pytest.raises(InvalidCredentialsError):
        authenticate_user(db_session, "user@example.com", "wrongpassword")


def test_authenticate_user_rejects_unknown_email(db_session):
    with pytest.raises(InvalidCredentialsError):
        authenticate_user(db_session, "missing@example.com", "supersecret")


def test_authenticate_user_hashes_password_even_for_unknown_email(db_session, monkeypatch):
    """Guards against a timing side-channel that would reveal which emails
    are registered: verify_password must run whether or not the user exists."""
    calls = []
    original_verify_password = auth_service_module.verify_password

    def spy_verify_password(password, encoded_hash):
        calls.append(encoded_hash)
        return original_verify_password(password, encoded_hash)

    monkeypatch.setattr(auth_service_module, "verify_password", spy_verify_password)

    with pytest.raises(InvalidCredentialsError):
        authenticate_user(db_session, "missing@example.com", "supersecret")

    assert len(calls) == 1
    assert calls[0] == auth_service_module._DUMMY_PASSWORD_HASH


def test_register_user_handles_concurrent_duplicate_insert(db_session, monkeypatch):
    """Simulates a race where two requests both pass the SELECT check before
    either commits; the DB's unique constraint must still be converted into
    EmailAlreadyRegisteredError instead of an unhandled IntegrityError."""
    register_user(db_session, "user@example.com", "supersecret", "5524981402661")

    original_execute = db_session.execute

    def fake_execute(*args, **kwargs):
        result = original_execute(*args, **kwargs)
        result.scalar_one_or_none = lambda: None  # pretend the SELECT found nothing
        return result

    monkeypatch.setattr(db_session, "execute", fake_execute)

    with pytest.raises(EmailAlreadyRegisteredError):
        register_user(db_session, "user@example.com", "anotherpassword", "5524981402661")


def test_get_notification_phone_number_returns_none_when_no_users(db_session):
    assert get_notification_phone_number(db_session) is None


def test_get_notification_phone_number_returns_none_when_no_user_has_one(db_session):
    db_session.add(UserModel(email="user@example.com", hashed_password="hash", phone_number=None))
    db_session.commit()

    assert get_notification_phone_number(db_session) is None


def test_get_notification_phone_number_returns_the_earliest_registered_with_one(db_session):
    register_user(db_session, "first@example.com", "supersecret", "5511111111111")
    register_user(db_session, "second@example.com", "supersecret", "5522222222222")

    assert get_notification_phone_number(db_session) == "5511111111111"


def test_get_notification_phone_number_skips_users_without_one(db_session):
    db_session.add(UserModel(email="nophone@example.com", hashed_password="hash", phone_number=None))
    db_session.commit()
    register_user(db_session, "haphone@example.com", "supersecret", "5533333333333")

    assert get_notification_phone_number(db_session) == "5533333333333"
