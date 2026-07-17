"""Alert history persistence, independent of FastAPI.

Alerts record that a detection happened and reference its saved image, so
the owner has a durable history even if a future WhatsApp delivery attempt
fails or a message is lost/deleted on their phone. Sending alerts via
WhatsApp is not implemented yet — this module only persists them.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Union

from sqlalchemy import select
from sqlalchemy.orm import Session

from web.db_models import AlertModel


def create_alert(db: Session, message: str, image_path: Union[str, Path]) -> AlertModel:
    alert = AlertModel(message=message, image_path=str(image_path))
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def list_alerts(db: Session, limit: int = 50, offset: int = 0) -> List[AlertModel]:
    """Return alerts ordered from most recent to oldest."""
    stmt = (
        select(AlertModel)
        .order_by(AlertModel.created_at.desc(), AlertModel.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars())
