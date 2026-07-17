"""YOLO11n-based person detection."""

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
    """Raised when the model fails to run inference on a frame."""


def select_device() -> str:
    """Select MPS when available, falling back to CPU."""
    return "mps" if torch.backends.mps.is_available() else "cpu"


class PersonDetector:
    """Loads YOLO11n once and detects people in frames.

    This class only performs inference and filtering. It does not save
    images, control cooldowns, or read environment variables directly.
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
        """Run inference on a frame and return only person detections.

        Automatically falls back to CPU if the current device raises a
        runtime error during inference (e.g. an unsupported MPS operation).

        Raises:
            InferenceError: If inference fails even after a CPU fallback
                attempt.
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
