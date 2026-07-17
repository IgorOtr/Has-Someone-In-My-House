"""SQLAlchemy engine/session wiring for the web dashboard's user store."""

from __future__ import annotations

import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

from web.auth_config import AuthConfig

logger = logging.getLogger(__name__)

Base = declarative_base()

# Additive columns introduced after a table's first release. `create_all`
# never alters an existing table, so an already-deployed database needs
# these applied by hand. Each entry: (table, column, DDL used to add it).
_ADDITIVE_COLUMNS = [
    ("users", "phone_number", "ALTER TABLE users ADD COLUMN phone_number VARCHAR(20)"),
]


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


def ensure_schema_migrations(engine: Engine) -> None:
    """Apply small additive schema changes that ``create_all`` cannot.

    ``Base.metadata.create_all`` only creates tables that do not exist yet;
    it never adds a column to a table that is already there. Call this
    after :func:`init_models` so a database created fresh in this same call
    already has every column and each check below is a no-op.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table, column, ddl in _ADDITIVE_COLUMNS:
        if table not in existing_tables:
            continue  # init_models just created it with every current column
        existing_columns = {col["name"] for col in inspector.get_columns(table)}
        if column in existing_columns:
            continue
        with engine.begin() as connection:
            connection.execute(text(ddl))
        logger.info("Added column '%s.%s'", table, column)
