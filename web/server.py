"""FastAPI application exposing a read-only view of saved detections.

This is a separate, optional process from the monitor (``run.py``). It does
not open the webcam, run inference, or control the monitor in any way — it
only lists, serves and lets you delete the JPEG files the monitor already
saved to ``IMAGE_DIRECTORY``. All of that, plus monitor start/stop, requires
a logged-in user (see ``/api/auth/*``).
"""

from __future__ import annotations

import logging
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, List

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import AppConfig
from web.alert_service import list_alerts
from web.auth_config import AuthConfig
from web.auth_service import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    authenticate_user,
    register_user,
)
from web.db import ensure_database_exists, init_models
from web.db_models import UserModel
from web.dependencies import (
    enforce_login_rate_limit,
    enforce_register_rate_limit,
    get_auth_settings,
    get_current_user,
    get_db,
    get_engine,
    get_gallery_service,
    get_monitor_manager,
    get_settings,
)
from web.gallery import GalleryService
from web.monitor_process import (
    MonitorAlreadyRunningError,
    MonitorNotRunningError,
    MonitorProcessManager,
)
from web.schemas import (
    AlertItem,
    DetectionItem,
    LoginRequest,
    MonitorStatusResponse,
    RegisterRequest,
    StatusResponse,
    TokenResponse,
    UserResponse,
)
from web.security import create_access_token

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    auth_settings = get_auth_settings()
    if auth_settings.uses_insecure_default_secret:
        logger.warning(
            "JWT_SECRET_KEY is using its insecure default value. Set a real "
            "secret in .env before exposing this dashboard beyond localhost."
        )
    ensure_database_exists(auth_settings)
    init_models(get_engine())
    yield


app = FastAPI(title="Person Detection Monitor API", lifespan=lifespan)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.post(
    "/api/auth/register",
    response_model=UserResponse,
    status_code=201,
    dependencies=[Depends(enforce_register_rate_limit)],
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    auth_settings: AuthConfig = Depends(get_auth_settings),
) -> UserResponse:
    if not auth_settings.allow_public_registration:
        raise HTTPException(status_code=403, detail="Public registration is disabled.")
    try:
        user = register_user(db, payload.email, payload.password)
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return UserResponse(id=user.id, email=user.email, created_at=user.created_at)


@app.post(
    "/api/auth/login",
    response_model=TokenResponse,
    dependencies=[Depends(enforce_login_rate_limit)],
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
    auth_settings: AuthConfig = Depends(get_auth_settings),
) -> TokenResponse:
    try:
        user = authenticate_user(db, payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    token = create_access_token(
        user.email, auth_settings.jwt_secret_key, auth_settings.jwt_expires_minutes
    )
    return TokenResponse(access_token=token)


@app.get("/api/auth/me", response_model=UserResponse)
def read_current_user(current_user: UserModel = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=current_user.id, email=current_user.email, created_at=current_user.created_at
    )


@app.get("/api/status", response_model=StatusResponse)
def read_status(
    settings: AppConfig = Depends(get_settings),
    gallery: GalleryService = Depends(get_gallery_service),
    current_user: UserModel = Depends(get_current_user),
) -> StatusResponse:
    latest = gallery.latest()
    return StatusResponse(
        total_detections=gallery.count(),
        latest_detection_at=latest.detected_at if latest else None,
        image_directory=str(settings.image_directory),
        confidence_threshold=settings.confidence_threshold,
        detection_window_size=settings.detection_window_size,
        minimum_positive_frames=settings.minimum_positive_frames,
        capture_delay_seconds=settings.capture_delay_seconds,
        capture_cooldown_seconds=settings.capture_cooldown_seconds,
        image_retention_hours=settings.image_retention_hours,
    )


@app.get("/api/detections", response_model=List[DetectionItem])
def list_detections(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    gallery: GalleryService = Depends(get_gallery_service),
    current_user: UserModel = Depends(get_current_user),
) -> List[DetectionItem]:
    items = gallery.list_detections(limit=limit, offset=offset)
    return [
        DetectionItem(
            filename=item.filename,
            detected_at=item.detected_at,
            size_bytes=item.size_bytes,
            image_url=f"/api/detections/{item.filename}/image",
        )
        for item in items
    ]


@app.get("/api/detections/{filename}/image")
def get_detection_image(
    filename: str,
    gallery: GalleryService = Depends(get_gallery_service),
    current_user: UserModel = Depends(get_current_user),
) -> FileResponse:
    path = gallery.resolve_path(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Detection image not found.")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)


@app.get("/api/alerts", response_model=List[AlertItem])
def list_alerts_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> List[AlertItem]:
    alerts = list_alerts(db, limit=limit, offset=offset)
    return [
        AlertItem(
            id=alert.id,
            message=alert.message,
            image_path=alert.image_path,
            image_url=f"/api/detections/{Path(alert.image_path).name}/image",
            sent=alert.sent,
            created_at=alert.created_at,
        )
        for alert in alerts
    ]


@app.delete("/api/detections/{filename}", status_code=204)
def delete_detection(
    filename: str,
    gallery: GalleryService = Depends(get_gallery_service),
    current_user: UserModel = Depends(get_current_user),
) -> None:
    if not gallery.delete(filename):
        raise HTTPException(status_code=404, detail="Detection image not found.")


@app.get("/api/monitor/status", response_model=MonitorStatusResponse)
def read_monitor_status(
    monitor: MonitorProcessManager = Depends(get_monitor_manager),
    current_user: UserModel = Depends(get_current_user),
) -> MonitorStatusResponse:
    return MonitorStatusResponse(running=monitor.is_running(), pid=monitor.pid())


@app.post("/api/monitor/start", response_model=MonitorStatusResponse)
def start_monitor(
    monitor: MonitorProcessManager = Depends(get_monitor_manager),
    current_user: UserModel = Depends(get_current_user),
) -> MonitorStatusResponse:
    try:
        pid = monitor.start()
    except MonitorAlreadyRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MonitorStatusResponse(running=True, pid=pid)


@app.post("/api/monitor/stop", response_model=MonitorStatusResponse)
def stop_monitor(
    monitor: MonitorProcessManager = Depends(get_monitor_manager),
    current_user: UserModel = Depends(get_current_user),
) -> MonitorStatusResponse:
    try:
        monitor.stop()
    except MonitorNotRunningError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MonitorStatusResponse(running=False, pid=None)


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
