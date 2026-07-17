"""Models ORM (SQLAlchemy) das tabelas da aplicação, salvas no MySQL."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from web.db import Base


class UserModel(Base):
    """Conta do dashboard: e-mail, senha (hash) e telefone para WhatsApp."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    # Nullable no banco para que adicionar esta coluna a uma tabela `users`
    # já implantada (via ensure_schema_migrations) nunca falhe nas linhas
    # existentes; todo cadastro novo sempre exige o telefone (ver RegisterRequest).
    phone_number = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AlertModel(Base):
    """Um registro durável de um alerta de detecção.

    Mantido independente do envio pelo WhatsApp, para que o proprietário
    nunca perca o histórico do que foi detectado, mesmo que uma mensagem
    falhe ao enviar ou seja apagada no celular dele.
    """

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message = Column(String(500), nullable=False)
    image_path = Column(String(1024), nullable=False)
    sent = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
