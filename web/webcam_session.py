"""Sessão de monitoramento por webcam do navegador (uma por conexão WebSocket).

Reaproveita os mesmos componentes do monitor físico (``app/``): o
``PersonDetector`` (YOLO), ``ImageManager`` (salva a imagem anotada) e
``AlertRecorder`` (grava o alerta e tenta o envio por WhatsApp) são
compartilhados entre sessões — só o ``DetectionTracker`` e o
``CaptureController`` são próprios de cada sessão, já que cada aba de
navegador representa uma "câmera" independente.

Este módulo não sabe nada de WebSocket/FastAPI: recebe um frame já
decodificado e devolve um dicionário pronto para virar JSON. Isso o torna
testável sem abrir conexão nenhuma.
"""

from __future__ import annotations

import logging
from typing import List

import numpy as np

from app.alert_recorder import AlertRecorder
from app.capture_controller import CaptureController
from app.detection_tracker import DetectionTracker
from app.detector import InferenceError, PersonDetector
from app.image_manager import ImageManager
from app.models import Detection

logger = logging.getLogger(__name__)

STATUS_MONITORING = "Monitoring"
STATUS_PERSON_DETECTED = "Person detected"
STATUS_DETECTION_CONFIRMED = "Detection confirmed"
STATUS_IMAGE_SAVED = "Image saved"
STATUS_COOLDOWN = "Cooldown"
STATUS_INFERENCE_ERROR = "Inference error"
STATUS_SAVE_ERROR = "Save error"


def _build_alert_message(detections: List[Detection]) -> str:
    """Monta a mensagem do alerta (nº de pessoas + confiança máxima).

    Mesmo formato usado por ``app/main.py`` para o monitor físico.
    """
    person_count = len(detections)
    highest_confidence = max((d.confidence for d in detections), default=0.0)
    plural = "s" if person_count != 1 else ""
    return (
        f"Pessoa detectada ({person_count} pessoa{plural}, "
        f"confiança máxima {highest_confidence:.0%})"
    )


class WebcamMonitorSession:
    """Estado de confirmação/cooldown de uma sessão de webcam do navegador.

    Uma instância nova deve ser criada por conexão WebSocket; o detector,
    o gerenciador de imagens e o gravador de alertas são compartilhados
    entre todas as sessões (injeção de dependência).
    """

    def __init__(
        self,
        detector: PersonDetector,
        image_manager: ImageManager,
        alert_recorder: AlertRecorder,
        window_size: int,
        minimum_positive_frames: int,
        cooldown_seconds: float,
        capture_delay_seconds: float,
    ) -> None:
        self._detector = detector
        self._image_manager = image_manager
        self._alert_recorder = alert_recorder
        self._tracker = DetectionTracker(
            window_size=window_size, minimum_positive_frames=minimum_positive_frames
        )
        self._capture_controller = CaptureController(
            cooldown_seconds=cooldown_seconds, capture_delay_seconds=capture_delay_seconds
        )

    def process_frame(self, frame: np.ndarray) -> dict:
        """Roda a detecção num frame e decide status/salvamento/alerta.

        Espelha a lógica do loop principal do monitor físico
        (``app/main.py``), adaptada para um frame por vez em vez de um
        loop contínuo de captura.

        Returns:
            Um dicionário serializável em JSON com ``status``,
            ``person_count`` e ``cooldown_remaining``, para o front desenhar
            o HUD.
        """
        status = STATUS_MONITORING

        try:
            detections = self._detector.detect(frame)
        except InferenceError as exc:
            logger.error("Inference error: %s", exc)
            return self._status_payload(STATUS_INFERENCE_ERROR, 0)

        person_present = len(detections) > 0
        self._tracker.update(person_present)
        if person_present:
            status = STATUS_PERSON_DETECTED

        if self._tracker.is_confirmed():
            status = STATUS_DETECTION_CONFIRMED
            self._capture_controller.notify_detection_confirmed()
            if self._capture_controller.is_capture_due():
                saved_path = self._image_manager.save_detection_image(frame, detections)
                if saved_path is not None:
                    self._capture_controller.notify_saved()
                    self._tracker.reset()
                    status = STATUS_IMAGE_SAVED
                    self._alert_recorder.record_alert(_build_alert_message(detections), saved_path)
                else:
                    status = STATUS_SAVE_ERROR
            elif not self._capture_controller.can_capture():
                status = STATUS_COOLDOWN
        else:
            self._capture_controller.cancel_pending_capture()

        return self._status_payload(status, len(detections))

    def _status_payload(self, status: str, person_count: int) -> dict:
        return {
            "status": status,
            "person_count": person_count,
            "cooldown_remaining": self._capture_controller.cooldown_remaining_seconds(),
        }
