"""SQLAlchemy engine/session wiring for the web dashboard's user store."""

from __future__ import annotations

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

from web.auth_config import AuthConfig

logger = logging.getLogger(__name__)

Base = declarative_base()


def ensure_database_exists(auth_config: AuthConfig) -> None:
    """Create the configured MySQL database if it does not already exist.

    ``auth_config.db_name`` is validated (letters/digits/underscore only) by
    :func:`web.auth_config.load_auth_config`, so it is safe to interpolate
    into the identifier here.
    """
    bootstrap_engine = create_engine(auth_config.server_database_url, isolation_level="AUTOCOMMIT")
    try:
        with bootstrap_engine.connect() as connection:
            connection.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{auth_config.db_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
        logger.info("Database '%s' is ready", auth_config.db_name)
    finally:
        bootstrap_engine.dispose()


def build_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True, future=True)


def build_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def init_models(engine: Engine) -> None:
    """Create all tables registered on ``Base`` that do not exist yet."""
    from web import db_models  # noqa: F401  (registers models on Base.metadata)

    Base.metadata.create_all(bind=engine)
