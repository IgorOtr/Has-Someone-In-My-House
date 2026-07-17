"""Configuração de autenticação e do banco MySQL do dashboard web.

Mantida separada de ``app/config.py`` (configuração do monitor da webcam)
porque essas opções só são relevantes para a camada web, que é opcional.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Mapping, Optional

from dotenv import load_dotenv


class AuthConfigError(Exception):
    """Levantada quando um valor de configuração de auth/banco é inválido."""


_DB_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")

_DEFAULTS: Mapping[str, str] = {
    "DB_HOST": "127.0.0.1",
    "DB_PORT": "3306",
    "DB_USER": "app_user",
    "DB_PASSWORD": "app_password",
    "DB_NAME": "app_database",
    "JWT_SECRET_KEY": "insecure-dev-secret-change-me",
    "JWT_EXPIRES_MINUTES": "120",
    "ALLOW_PUBLIC_REGISTRATION": "true",
}

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}

_INSECURE_DEFAULT_SECRET = _DEFAULTS["JWT_SECRET_KEY"]


@dataclass(frozen=True)
class AuthConfig:
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str
    jwt_secret_key: str
    jwt_expires_minutes: int
    allow_public_registration: bool

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def server_database_url(self) -> str:
        """URL de conexão sem um banco selecionado, usada para criá-lo se não existir."""
        return f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/"

    @property
    def uses_insecure_default_secret(self) -> bool:
        return self.jwt_secret_key == _INSECURE_DEFAULT_SECRET


def _get_raw(env: Mapping[str, str], key: str) -> str:
    value = env.get(key)
    if value is None or value.strip() == "":
        return _DEFAULTS[key]
    return value.strip()


def _get_int(env: Mapping[str, str], key: str) -> int:
    raw = _get_raw(env, key)
    try:
        return int(raw)
    except ValueError as exc:
        raise AuthConfigError(f"Invalid value for {key}: {raw!r} is not a valid integer.") from exc


def _get_bool(env: Mapping[str, str], key: str) -> bool:
    raw = _get_raw(env, key).lower()
    if raw in _TRUE_VALUES:
        return True
    if raw in _FALSE_VALUES:
        return False
    raise AuthConfigError(f"Invalid value for {key}: {raw!r} is not a valid boolean.")


def load_auth_config(env: Optional[Mapping[str, str]] = None) -> AuthConfig:
    """Carrega, converte e valida a configuração de autenticação/banco.

    Args:
        env: Mapeamento opcional de onde ler os valores. Por padrão usa
            ``os.environ`` após carregar um arquivo ``.env``, principalmente
            para os testes injetarem valores sem depender de variáveis de
            ambiente reais.
    """
    if env is None:
        load_dotenv()
        env = os.environ

    db_host = _get_raw(env, "DB_HOST")
    db_port = _get_int(env, "DB_PORT")
    db_user = _get_raw(env, "DB_USER")
    db_password = _get_raw(env, "DB_PASSWORD")
    db_name = _get_raw(env, "DB_NAME")
    jwt_secret_key = _get_raw(env, "JWT_SECRET_KEY")
    jwt_expires_minutes = _get_int(env, "JWT_EXPIRES_MINUTES")
    allow_public_registration = _get_bool(env, "ALLOW_PUBLIC_REGISTRATION")

    if db_port <= 0:
        raise AuthConfigError("DB_PORT must be greater than 0.")
    if not _DB_NAME_PATTERN.match(db_name):
        raise AuthConfigError("DB_NAME must contain only letters, numbers and underscores.")
    if jwt_expires_minutes <= 0:
        raise AuthConfigError("JWT_EXPIRES_MINUTES must be greater than 0.")

    return AuthConfig(
        db_host=db_host,
        db_port=db_port,
        db_user=db_user,
        db_password=db_password,
        db_name=db_name,
        jwt_secret_key=jwt_secret_key,
        jwt_expires_minutes=jwt_expires_minutes,
        allow_public_registration=allow_public_registration,
    )
