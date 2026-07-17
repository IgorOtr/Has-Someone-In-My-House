"""Modelos Pydantic de requisição/resposta da API do dashboard web."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

# Código do país + DDD + número, só dígitos, sem "+"/espaços/traços —
# ex.: "5524981402661" (55 = Brasil, 24 = DDD, 981402661 = número).
_PHONE_NUMBER_PATTERN = re.compile(r"^\d{10,15}$")


def _validate_phone_number(value: str) -> str:
    if not _PHONE_NUMBER_PATTERN.match(value):
        raise ValueError(
            "phone_number must contain only digits (country code + area code "
            "+ number), e.g. 5524981402661."
        )
    return value


class RegisterRequest(BaseModel):
    """Corpo da requisição de cadastro de um novo usuário."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone_number: str = Field(min_length=10, max_length=15)

    @field_validator("phone_number")
    @classmethod
    def _check_phone_number(cls, value: str) -> str:
        return _validate_phone_number(value)


class LoginRequest(BaseModel):
    """Corpo da requisição de login."""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Dados públicos de um usuário (sem a senha)."""

    id: int
    email: str
    phone_number: Optional[str]
    created_at: datetime


class TokenResponse(BaseModel):
    """Resposta do login: o token de acesso JWT."""

    access_token: str
    token_type: str = "bearer"


class DetectionItem(BaseModel):
    """Um item da lista de detecções salvas."""

    filename: str
    detected_at: datetime
    size_bytes: int
    image_url: str


class AlertItem(BaseModel):
    """Um item do histórico de alertas."""

    id: int
    message: str
    image_path: str
    image_url: str
    sent: bool
    created_at: datetime


class MonitorStatusResponse(BaseModel):
    """Estado atual do processo do monitor."""

    running: bool
    pid: Optional[int]


class StatusResponse(BaseModel):
    """Resumo do estado do monitor e da configuração ativa."""

    total_detections: int
    latest_detection_at: Optional[datetime]
    image_directory: str
    confidence_threshold: float
    detection_window_size: int
    minimum_positive_frames: int
    capture_delay_seconds: float
    capture_cooldown_seconds: float
    image_retention_hours: float
