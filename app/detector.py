"""Detecção de pessoas usando o modelo YOLO11n."""

from __future__ import annotations

import logging
from typing import List

import numpy as np
import torch
from ultralytics import YOLO

from app.models import Detection

logger = logging.getLogger(__name__)

PERSON_CLASS_ID = 0
PERSON_CLASS_NAME = "person"


class InferenceError(Exception):
    """Levantada quando o modelo falha ao rodar a inferência em um frame."""


def select_device() -> str:
    """Seleciona MPS quando disponível, com fallback para CPU."""
    return "mps" if torch.backends.mps.is_available() else "cpu"


class PersonDetector:
    """Carrega o YOLO11n uma única vez e detecta pessoas nos frames.

    Esta classe só executa inferência e filtragem. Não salva imagens, não
    controla cooldown e não lê variáveis de ambiente diretamente.
    """

    def __init__(
        self,
        model_path: str,
        image_size: int,
        confidence_threshold: float,
        device: str | None = None,
    ) -> None:
        self._image_size = image_size
        self._confidence_threshold = confidence_threshold
        self._device = device or select_device()

        logger.info("Loading YOLO model from %s", model_path)
        self._model = YOLO(model_path)
        logger.info("Model loaded. Selected device: %s", self._device.upper())

    @property
    def device(self) -> str:
        return self._device

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """Roda a inferência em um frame e retorna só as detecções de pessoas.

        Cai automaticamente para CPU se o dispositivo atual levantar um
        erro em tempo de execução durante a inferência (ex.: operação não
        suportada pelo MPS).

        Raises:
            InferenceError: Se a inferência falhar mesmo após a tentativa
                de fallback para CPU.
        """
        try:
            return self._run_inference(frame, self._device)
        except RuntimeError as exc:
            if self._device != "cpu":
                logger.warning(
                    "Inference failed on %s (%s). Falling back to CPU.",
                    self._device.upper(),
                    exc,
                )
                self._device = "cpu"
                try:
                    return self._run_inference(frame, self._device)
                except RuntimeError as cpu_exc:
                    raise InferenceError(str(cpu_exc)) from cpu_exc
            raise InferenceError(str(exc)) from exc

    def _run_inference(self, frame: np.ndarray, device: str) -> List[Detection]:
        results = self._model.predict(
            source=frame,
            imgsz=self._image_size,
            conf=self._confidence_threshold,
            classes=[PERSON_CLASS_ID],
            device=device,
            verbose=False,
        )

        detections: List[Detection] = []
        if not results:
            return detections

        boxes = results[0].boxes
        if boxes is None:
            return detections

        for box in boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            if class_id != PERSON_CLASS_ID or confidence < self._confidence_threshold:
                continue
            x1, y1, x2, y2 = (int(value) for value in box.xyxy[0])
            detections.append(
                Detection(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    confidence=confidence,
                    class_id=class_id,
                    class_name=PERSON_CLASS_NAME,
                )
            )
        return detections
