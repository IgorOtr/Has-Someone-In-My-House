"""Provedores de dependências do FastAPI para o dashboard web."""

from __future__ import annotations

from functools import lru_cache
from typing import Iterator

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import AppConfig, load_config
from web.auth_config import AuthConfig, load_auth_config
from web.db import build_engine, build_session_factory
from web.db_models import UserModel
from web.gallery import GalleryService
from web.monitor_process import MonitorProcessManager
from web.rate_limiter import InMemoryRateLimiter
from web.security import decode_access_token


@lru_cache
def get_settings() -> AppConfig:
    """Carrega a configuração do monitor uma única vez e a reutiliza."""
    return load_config()


def get_gallery_service(settings: AppConfig = Depends(get_settings)) -> GalleryService:
    """Cria um GalleryService vinculado ao diretório de imagens configurado."""
    return GalleryService(settings.image_directory, settings.image_format)


_monitor_manager = MonitorProcessManager()


def get_monitor_manager() -> MonitorProcessManager:
    """Retorna a única instância do gerenciador do monitor, compartilhada no processo."""
    return _monitor_manager


@lru_cache
def get_auth_settings() -> AuthConfig:
    """Carrega a configuração de auth/banco uma vez e a reutiliza entre requisições."""
    return load_auth_config()


@lru_cache
def get_engine() -> Engine:
    """Cria (uma vez) a engine do SQLAlchemy usada por toda a aplicação."""
    return build_engine(get_auth_settings().database_url)


@lru_cache
def _get_session_factory() -> sessionmaker:
    return build_session_factory(get_engine())


def get_db() -> Iterator[Session]:
    """Fornece uma sessão do SQLAlchemy, fechando-a ao final da requisição."""
    session = _get_session_factory()()
    try:
        yield session
    finally:
        session.close()


_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    auth_settings: AuthConfig = Depends(get_auth_settings),
    db: Session = Depends(get_db),
) -> UserModel:
    """Resolve o usuário autenticado a partir do token ``Authorization: Bearer``."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    try:
        email = decode_access_token(credentials.credentials, auth_settings.jwt_secret_key)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token.") from exc

    user = db.execute(select(UserModel).where(UserModel.email == email)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found.")
    return user


# Um limitador por rota (login/cadastro), compartilhado entre as requisições do processo.
_login_rate_limiter = InMemoryRateLimiter(max_attempts=5, window_seconds=60)
_register_rate_limiter = InMemoryRateLimiter(max_attempts=5, window_seconds=60)


def get_login_rate_limiter() -> InMemoryRateLimiter:
    """Retorna o rate limiter compartilhado da rota de login."""
    return _login_rate_limiter


def get_register_rate_limiter() -> InMemoryRateLimiter:
    """Retorna o rate limiter compartilhado da rota de cadastro."""
    return _register_rate_limiter


def _client_key(request: Request) -> str:
    """Chave usada para limitar tentativas: o IP do cliente da requisição."""
    return request.client.host if request.client else "unknown"


def enforce_login_rate_limit(
    request: Request, limiter: InMemoryRateLimiter = Depends(get_login_rate_limiter)
) -> None:
    """Bloqueia a requisição com 429 se o IP excedeu o limite de tentativas de login."""
    if not limiter.is_allowed(_client_key(request)):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again in a minute.")


def enforce_register_rate_limit(
    request: Request, limiter: InMemoryRateLimiter = Depends(get_register_rate_limiter)
) -> None:
    """Bloqueia a requisição com 429 se o IP excedeu o limite de tentativas de cadastro."""
    if not limiter.is_allowed(_client_key(request)):
        raise HTTPException(
            status_code=429, detail="Too many registration attempts. Try again in a minute."
        )
