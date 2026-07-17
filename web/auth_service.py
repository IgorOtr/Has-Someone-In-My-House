"""Lógica de cadastro e autenticação de usuários, independente do FastAPI."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from web.db_models import UserModel
from web.security import hash_password, verify_password


class EmailAlreadyRegisteredError(Exception):
    """Levantada ao tentar cadastrar um e-mail que já está em uso."""


class InvalidCredentialsError(Exception):
    """Levantada quando as credenciais de login não batem com nenhum usuário."""


# Usado só para manter o tempo de resposta de authenticate_user
# praticamente constante, exista ou não o e-mail — assim o tempo de
# resposta não revela quais e-mails estão cadastrados. Nunca é comparado
# com sucesso; só serve para gastar o mesmo tempo de hash.
_DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing-safety")


def register_user(db: Session, email: str, password: str, phone_number: str) -> UserModel:
    """Cria um novo usuário com senha em hash. Levanta erro se o e-mail já existir."""
    normalized_email = email.strip().lower()

    existing = db.execute(
        select(UserModel).where(UserModel.email == normalized_email)
    ).scalar_one_or_none()
    if existing is not None:
        raise EmailAlreadyRegisteredError(f"Email {normalized_email} is already registered.")

    user = UserModel(
        email=normalized_email,
        hashed_password=hash_password(password),
        phone_number=phone_number,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        # Duas tentativas de cadastro simultâneas com o mesmo e-mail podem
        # passar pela checagem SELECT acima; a constraint UNIQUE do banco
        # é a garantia real contra a corrida.
        db.rollback()
        raise EmailAlreadyRegisteredError(
            f"Email {normalized_email} is already registered."
        ) from exc
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> UserModel:
    """Verifica e-mail/senha e retorna o usuário. Levanta erro se inválidos."""
    normalized_email = email.strip().lower()

    user = db.execute(
        select(UserModel).where(UserModel.email == normalized_email)
    ).scalar_one_or_none()

    # Sempre roda a verificação de senha, mesmo para e-mail desconhecido,
    # para o tempo de resposta não vazar se o e-mail está cadastrado.
    hash_to_check = user.hashed_password if user is not None else _DUMMY_PASSWORD_HASH
    password_matches = verify_password(password, hash_to_check)

    if user is None or not password_matches:
        raise InvalidCredentialsError("Invalid email or password.")
    return user


def get_notification_phone_number(db: Session) -> Optional[str]:
    """Retorna o telefone para onde enviar os alertas do WhatsApp.

    Esta aplicação não tem uma flag explícita de "proprietário", então o
    usuário cadastrado há mais tempo que tenha um telefone configurado é
    tratado como o destinatário. Retorna None se nenhum usuário tiver um
    telefone configurado ainda.
    """
    stmt = (
        select(UserModel.phone_number)
        .where(UserModel.phone_number.is_not(None))
        .order_by(UserModel.id.asc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()
