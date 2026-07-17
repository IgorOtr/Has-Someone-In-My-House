"""Rotas de autenticação: cadastro, login e dados do usuário logado."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from web.auth_config import AuthConfig
from web.auth_service import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    authenticate_user,
    register_user,
)
from web.db_models import UserModel
from web.dependencies import (
    enforce_login_rate_limit,
    enforce_register_rate_limit,
    get_auth_settings,
    get_current_user,
    get_db,
)
from web.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from web.security import create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201,
    dependencies=[Depends(enforce_register_rate_limit)],
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    auth_settings: AuthConfig = Depends(get_auth_settings),
) -> UserResponse:
    """Cria uma nova conta (se o cadastro público estiver habilitado)."""
    if not auth_settings.allow_public_registration:
        raise HTTPException(status_code=403, detail="Public registration is disabled.")
    try:
        user = register_user(db, payload.email, payload.password, payload.phone_number)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return UserResponse(
        id=user.id, email=user.email, phone_number=user.phone_number, created_at=user.created_at
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(enforce_login_rate_limit)],
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
    auth_settings: AuthConfig = Depends(get_auth_settings),
) -> TokenResponse:
    """Autentica o usuário e retorna um token de acesso (JWT)."""
    try:
        user = authenticate_user(db, payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    token = create_access_token(
        user.email, auth_settings.jwt_secret_key, auth_settings.jwt_expires_minutes
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: UserModel = Depends(get_current_user)) -> UserResponse:
    """Retorna os dados do usuário autenticado na requisição atual."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        phone_number=current_user.phone_number,
        created_at=current_user.created_at,
    )
