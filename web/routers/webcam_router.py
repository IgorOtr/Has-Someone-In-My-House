"""Rota de WebSocket para monitoramento pela webcam do navegador.

Cada conexão representa uma "câmera" independente: o navegador do usuário
logado envia frames da própria webcam, e o servidor roda a mesma detecção
de pessoas do monitor físico (ver ``web/webcam_session.py``).
"""

from __future__ import annotations

import asyncio
import logging

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.alert_recorder import AlertRecorder
from app.config import AppConfig
from app.detector import PersonDetector
from app.image_manager import ImageManager
from web.auth_config import AuthConfig
from web.dependencies import (
    get_alert_recorder,
    get_auth_settings,
    get_db,
    get_detector_lock,
    get_image_manager,
    get_person_detector,
    get_settings,
    resolve_user_from_token,
)
from web.webcam_session import WebcamMonitorSession

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webcam"])

# Tempo máximo de espera pela primeira mensagem (autenticação) antes de fechar.
_AUTH_TIMEOUT_SECONDS = 10.0


@router.websocket("/ws/webcam")
async def webcam_monitor_ws(
    websocket: WebSocket,
    settings: AppConfig = Depends(get_settings),
    auth_settings: AuthConfig = Depends(get_auth_settings),
    db: Session = Depends(get_db),
    detector: PersonDetector = Depends(get_person_detector),
    image_manager: ImageManager = Depends(get_image_manager),
    alert_recorder: AlertRecorder = Depends(get_alert_recorder),
    detector_lock: asyncio.Lock = Depends(get_detector_lock),
) -> None:
    """Recebe frames da webcam do navegador e roda a detecção de pessoas.

    Protocolo:
    1. A primeira mensagem deve ser um JSON ``{"token": "<jwt>"}`` (o token
       não vai na URL para não vazar em logs de acesso/proxy).
    2. Cada mensagem seguinte é um frame JPEG binário.
    3. Para cada frame processado, o servidor responde um JSON de status
       (``status``, ``person_count``, ``cooldown_remaining``).
    """
    await websocket.accept()

    try:
        auth_message = await asyncio.wait_for(
            websocket.receive_json(), timeout=_AUTH_TIMEOUT_SECONDS
        )
    except WebSocketDisconnect:
        return
    except (asyncio.TimeoutError, ValueError):
        await websocket.close(code=4401, reason="Authentication timed out or malformed.")
        return

    token = auth_message.get("token") if isinstance(auth_message, dict) else None
    if not token:
        await websocket.close(code=4401, reason="Missing token.")
        return

    try:
        user = resolve_user_from_token(token, auth_settings, db)
    except HTTPException:
        await websocket.close(code=4401, reason="Invalid or expired token.")
        return
    finally:
        # A sessão do banco só é usada para autenticar; libera a conexão
        # de volta ao pool em vez de segurá-la pela vida inteira do WebSocket.
        db.close()

    logger.info("Webcam monitor session started for %s", user.email)

    session = WebcamMonitorSession(
        detector=detector,
        image_manager=image_manager,
        alert_recorder=alert_recorder,
        window_size=settings.detection_window_size,
        minimum_positive_frames=settings.minimum_positive_frames,
        cooldown_seconds=settings.capture_cooldown_seconds,
        capture_delay_seconds=settings.capture_delay_seconds,
    )

    try:
        while True:
            frame_bytes = await websocket.receive_bytes()
            frame = cv2.imdecode(np.frombuffer(frame_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue

            # Serializa o acesso ao modelo entre sessões simultâneas.
            async with detector_lock:
                payload = await asyncio.to_thread(session.process_frame, frame)

            await websocket.send_json(payload)
    except WebSocketDisconnect:
        logger.info("Webcam monitor session ended for %s", user.email)
