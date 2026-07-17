"""Rotas de status e das imagens de detecção salvas pelo monitor."""

from __future__ import annotations

import mimetypes
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.config import AppConfig
from web.db_models import UserModel
from web.dependencies import get_current_user, get_gallery_service, get_settings
from web.gallery import GalleryService
from web.schemas import DetectionItem, StatusResponse

router = APIRouter(prefix="/api", tags=["detections"])


@router.get("/status", response_model=StatusResponse)
def read_status(
    settings: AppConfig = Depends(get_settings),
    gallery: GalleryService = Depends(get_gallery_service),
    current_user: UserModel = Depends(get_current_user),
) -> StatusResponse:
    """Resumo do estado atual: total de detecções, última detecção e configuração ativa."""
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


@router.get("/detections", response_model=List[DetectionItem])
def list_detections(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    gallery: GalleryService = Depends(get_gallery_service),
    current_user: UserModel = Depends(get_current_user),
) -> List[DetectionItem]:
    """Lista paginada das detecções salvas, da mais recente para a mais antiga."""
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


@router.get("/detections/{filename}/image")
def get_detection_image(
    filename: str,
    gallery: GalleryService = Depends(get_gallery_service),
    current_user: UserModel = Depends(get_current_user),
) -> FileResponse:
    """Serve o arquivo JPEG de uma detecção específica."""
    path = gallery.resolve_path(filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Detection image not found.")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)


@router.delete("/detections/{filename}", status_code=204)
def delete_detection(
    filename: str,
    gallery: GalleryService = Depends(get_gallery_service),
    current_user: UserModel = Depends(get_current_user),
) -> None:
    """Remove uma imagem de detecção salva."""
    if not gallery.delete(filename):
        raise HTTPException(status_code=404, detail="Detection image not found.")
