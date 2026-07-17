"""Tests for web.db.ensure_schema_migrations using in-memory SQLite (no MySQL).

`Base.metadata.create_all` never alters an existing table, so upgrading a
database created before a new column existed needs this separate step.
"""

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from web.db import ensure_schema_migrations


def make_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def create_legacy_users_table(engine) -> None:
    """Simulates a `users` table created before `phone_number` existed."""
    metadata = MetaData()
    Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("email", String(255), unique=True, nullable=False),
        Column("hashed_password", String(255), nullable=False),
    )
    metadata.create_all(engine)


def test_adds_phone_number_column_to_an_existing_users_table():
    engine = make_engine()
    create_legacy_users_table(engine)

    ensure_schema_migrations(engine)

    columns = {col["name"] for col in inspect(engine).get_columns("users")}
    assert "phone_number" in columns


def test_preserves_existing_rows_when_adding_the_column():
    engine = make_engine()
    create_legacy_users_table(engine)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (email, hashed_password) VALUES ('user@example.com', 'hash')")
        )

    ensure_schema_migrations(engine)

    with engine.connect() as connection:
        row = connection.execute(text("SELECT email, phone_number FROM users")).first()
    assert row.email == "user@example.com"
    assert row.phone_number is None


def test_is_a_no_op_when_the_column_already_exists():
    engine = make_engine()
    create_legacy_users_table(engine)
    ensure_schema_migrations(engine)

    ensure_schema_migrations(engine)  # should not raise on the second run

    columns = [col["name"] for col in inspect(engine).get_columns("users")]
    assert columns.count("phone_number") == 1


def test_is_a_no_op_when_the_table_does_not_exist_yet():
    engine = make_engine()

    ensure_schema_migrations(engine)  # should not raise

    assert "users" not in inspect(engine).get_table_names()
