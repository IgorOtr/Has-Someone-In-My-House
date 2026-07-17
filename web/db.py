"""Configuração da engine/sessão do SQLAlchemy para as tabelas do dashboard."""

from __future__ import annotations

import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

from web.auth_config import AuthConfig

logger = logging.getLogger(__name__)

Base = declarative_base()

# Colunas aditivas introduzidas depois do primeiro release de cada tabela.
# `create_all` nunca altera uma tabela existente, então um banco já
# implantado precisa disso aplicado à mão. Cada item: (tabela, coluna, DDL
# usado para adicioná-la).
_ADDITIVE_COLUMNS = [
    ("users", "phone_number", "ALTER TABLE users ADD COLUMN phone_number VARCHAR(20)"),
]


def ensure_database_exists(auth_config: AuthConfig) -> None:
    """Cria o banco MySQL configurado, se ele ainda não existir.

    ``auth_config.db_name`` já foi validado (só letras/dígitos/underscore)
    por :func:`web.auth_config.load_auth_config`, então é seguro
    interpolá-lo diretamente no identificador aqui.
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
    """Cria a engine do SQLAlchemy usada para conectar ao MySQL."""
    return create_engine(database_url, pool_pre_ping=True, future=True)


def build_session_factory(engine: Engine) -> sessionmaker:
    """Cria a fábrica de sessões (sessionmaker) vinculada à engine informada."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def init_models(engine: Engine) -> None:
    """Cria todas as tabelas registradas em ``Base`` que ainda não existem."""
    from web import db_models  # noqa: F401  (registra os models em Base.metadata)

    Base.metadata.create_all(bind=engine)


def ensure_schema_migrations(engine: Engine) -> None:
    """Aplica pequenas mudanças aditivas de schema que o ``create_all`` não cobre.

    ``Base.metadata.create_all`` só cria tabelas que ainda não existem;
    nunca adiciona uma coluna a uma tabela que já está lá. Chame esta
    função depois de :func:`init_models`, assim um banco criado do zero
    nesta mesma chamada já tem todas as colunas e cada checagem abaixo
    vira um no-op.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table, column, ddl in _ADDITIVE_COLUMNS:
        if table not in existing_tables:
            continue  # init_models acabou de criá-la já com todas as colunas atuais
        existing_columns = {col["name"] for col in inspector.get_columns(table)}
        if column in existing_columns:
            continue
        with engine.begin() as connection:
            connection.execute(text(ddl))
        logger.info("Added column '%s.%s'", table, column)
