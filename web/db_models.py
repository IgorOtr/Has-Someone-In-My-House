"""SQLAlchemy ORM models for the application's MySQL-backed tables."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from web.db import Base


class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    # Nullable at the DB level so adding this column to an already-deployed
    # `users` table (via ensure_schema_migrations) never fails on existing
    # rows; new registrations always require it (see RegisterRequest).
    phone_number = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AlertModel(Base):
    """A durable record of a detection alert.

    Kept independently of WhatsApp delivery (not implemented yet) so the
    owner never loses the history of what was detected, even if a message
    fails to send or gets deleted on their phone.
    """

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message = Column(String(500), nullable=False)
    image_path = Column(String(1024), nullable=False)
    sent = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
