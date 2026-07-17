"""Pydantic response models for the web dashboard API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
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
