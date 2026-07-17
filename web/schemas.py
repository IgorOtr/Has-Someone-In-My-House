"""Pydantic response models for the web dashboard API."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

# Country code + area code + number, digits only, no "+"/spaces/dashes —
# e.g. "5524981402661" (55 = Brazil, 24 = area code, 981402661 = number).
_PHONE_NUMBER_PATTERN = re.compile(r"^\d{10,15}$")


def _validate_phone_number(value: str) -> str:
    if not _PHONE_NUMBER_PATTERN.match(value):
        raise ValueError(
            "phone_number must contain only digits (country code + area code "
            "+ number), e.g. 5524981402661."
        )
    return value


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone_number: str = Field(min_length=10, max_length=15)

    @field_validator("phone_number")
    @classmethod
    def _check_phone_number(cls, value: str) -> str:
        return _validate_phone_number(value)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    phone_number: Optional[str]
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DetectionItem(BaseModel):
    filename: str
    detected_at: datetime
    size_bytes: int
    image_url: str


class AlertItem(BaseModel):
    id: int
    message: str
    image_path: str
    image_url: str
    sent: bool
    created_at: datetime


class MonitorStatusResponse(BaseModel):
    running: bool
    pid: Optional[int]


class StatusResponse(BaseModel):
    total_detections: int
    latest_detection_at: Optional[datetime]
    image_directory: str
    confidence_threshold: float
    detection_window_size: int
    minimum_positive_frames: int
    capture_delay_seconds: float
    capture_cooldown_seconds: float
    image_retention_hours: float
