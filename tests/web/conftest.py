"""Shared fixtures for the web dashboard test suite.

Every test in this package uses an in-memory SQLite database instead of the
real MySQL instance: the FastAPI app's ``get_db`` and ``get_auth_settings``
dependencies are overridden here so no test ever needs MySQL running.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from web import db_models  # noqa: F401  (registers UserModel on Base.metadata)
from web.auth_config import AuthConfig
from web.db import Base
from web.dependencies import (
    get_auth_settings,
    get_db,
    get_login_rate_limiter,
    get_register_rate_limiter,
)
from web.server import app

TEST_AUTH_SETTINGS = AuthConfig(
    db_host="unused",
    db_port=3306,
    db_user="unused",
    db_password="unused",
    db_name="unused",
    jwt_secret_key="test-only-secret-key",
    jwt_expires_minutes=60,
    allow_public_registration=True,
)


@pytest.fixture
def db_session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    yield factory
    engine.dispose()


@pytest.fixture(autouse=True)
def override_auth_dependencies(db_session_factory):
    def _get_test_db():
        session = db_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_test_db
    app.dependency_overrides[get_auth_settings] = lambda: TEST_AUTH_SETTINGS
    get_login_rate_limiter().reset()
    get_register_rate_limiter().reset()
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_auth_settings, None)
