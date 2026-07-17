"""Persistência do histórico de alertas, independente do FastAPI.

Os alertas registram que uma detecção aconteceu e referenciam a imagem
salva, para o proprietário ter um histórico durável mesmo se uma tentativa
de envio pelo WhatsApp falhar ou a mensagem se perder/for apagada no
celular dele. O envio em si mora em ``web.whatsapp_client``; este módulo
só persiste os alertas e o status de entrega deles.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Union

from sqlalchemy import select
from sqlalchemy.orm import Session

from web.db_models import AlertModel


def create_alert(db: Session, message: str, image_path: Union[str, Path]) -> AlertModel:
    """Cria e salva um novo alerta (não enviado ainda) no banco."""
    alert = AlertModel(message=message, image_path=str(image_path))
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def list_alerts(db: Session, limit: int = 50, offset: int = 0) -> List[AlertModel]:
    """Retorna os alertas ordenados do mais recente para o mais antigo."""
    stmt = (
        select(AlertModel)
        .order_by(AlertModel.created_at.desc(), AlertModel.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars())


def mark_alert_sent(db: Session, alert_id: int) -> None:
    """Marca a flag ``sent`` do alerta como True após um envio bem-sucedido.

    Não faz nada, silenciosamente, se o alerta não existir mais (ex.:
    apagado entre a criação e o envio).
    """
    alert = db.get(AlertModel, alert_id)
    if alert is None:
        return
    alert.sent = True
    db.commit()
