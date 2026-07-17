"""User registration and authentication logic, independent of FastAPI."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from web.db_models import UserModel
from web.security import hash_password, verify_password


class EmailAlreadyRegisteredError(Exception):
    """Raised when trying to register an email that is already in use."""


class InvalidCredentialsError(Exception):
    """Raised when login credentials do not match any user."""


# Used only to keep authenticate_user's response time roughly constant
# whether or not the email exists, so timing cannot reveal registered
# emails. Never compared against successfully; it pads out the hashing cost.
_DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing-safety")


def register_user(db: Session, email: str, password: str, phone_number: str) -> UserModel:
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
        # Two concurrent registrations for the same email can both pass the
        # SELECT check above; the DB's unique constraint is the real guard.
        db.rollback()
        raise EmailAlreadyRegisteredError(
            f"Email {normalized_email} is already registered."
        ) from exc
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> UserModel:
    normalized_email = email.strip().lower()

    user = db.execute(
        select(UserModel).where(UserModel.email == normalized_email)
    ).scalar_one_or_none()

    # Always run password verification, even for an unknown email, so the
    # response time does not leak whether the email is registered.
    hash_to_check = user.hashed_password if user is not None else _DUMMY_PASSWORD_HASH
    password_matches = verify_password(password, hash_to_check)

    if user is None or not password_matches:
        raise InvalidCredentialsError("Invalid email or password.")
    return user
