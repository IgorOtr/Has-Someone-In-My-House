"""Rota do histórico de alertas."""

from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from web.alert_service import list_alerts
from web.db_models import UserModel
from web.dependencies import get_current_user, get_db
from web.schemas import AlertItem

router = APIRouter(prefix="/api", tags=["alerts"])


@router.get("/alerts", response_model=List[AlertItem])
def list_alerts_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
) -> List[AlertItem]:
    """Lista paginada do histórico de alertas, do mais recente para o mais antigo."""
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
