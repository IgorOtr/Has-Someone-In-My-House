"""Anotação, persistência e limpeza por retenção das imagens de detecção."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from app.models import Detection

logger = logging.getLogger(__name__)

_BOX_COLOR = (0, 220, 0)
_TEXT_COLOR = (0, 220, 0)
_HEADER_COLOR = (0, 220, 255)
_FONT = cv2.FONT_HERSHEY_SIMPLEX


class ImageManager:
    """Salva imagens de detecção anotadas e remove as antigas.

    Esta classe não depende do modelo YOLO; ela só consome valores simples
    de :class:`~app.models.Detection`.
    """

    def __init__(
        self,
        image_directory: Path,
        image_format: str,
        jpeg_quality: int,
        retention_hours: float,
    ) -> None:
        self._image_directory = Path(image_directory)
        self._image_format = image_format.lower().lstrip(".")
        self._jpeg_quality = jpeg_quality
        self._retention_seconds = retention_hours * 3600
        self._ensure_directory_exists()

    def _ensure_directory_exists(self) -> None:
        self._image_directory.mkdir(parents=True, exist_ok=True)

    def save_detection_image(
        self, frame: np.ndarray, detections: List[Detection]
    ) -> Optional[Path]:
        """Anota uma cópia do frame e a salva como JPEG.

        Returns:
            O caminho completo do arquivo salvo, ou ``None`` se o
            salvamento falhar. Em caso de falha, nenhuma exceção é
            levantada, para que quem chamou continue monitorando a webcam.
        """
        annotated = self._annotate_frame(frame, detections)
        file_path = self._build_unique_path()

        try:
            self._ensure_directory_exists()
            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), self._jpeg_quality]
            success = cv2.imwrite(str(file_path), annotated, encode_params)
        except Exception:
            logger.exception("Error writing detection image to %s", file_path)
            return None

        if not success:
            logger.error("cv2.imwrite reported failure for %s", file_path)
            return None

        logger.info("Detection image saved at %s", file_path)
        return file_path

    def _annotate_frame(
        self, frame: np.ndarray, detections: List[Detection]
    ) -> np.ndarray:
        annotated = frame.copy()

        for detection in detections:
            cv2.rectangle(
                annotated,
                (detection.x1, detection.y1),
                (detection.x2, detection.y2),
                _BOX_COLOR,
                2,
            )
            label = f"{detection.class_name} {detection.confidence:.2f}"
            label_y = max(detection.y1 - 8, 12)
            cv2.putText(
                annotated,
                label,
                (detection.x1, label_y),
                _FONT,
                0.5,
                _TEXT_COLOR,
                2,
                cv2.LINE_AA,
            )

        timestamp_text = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
        cv2.putText(
            annotated,
            timestamp_text,
            (10, 25),
            _FONT,
            0.6,
            _HEADER_COLOR,
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            annotated,
            "Pessoa Detectada",
            (10, 50),
            _FONT,
            0.6,
            _HEADER_COLOR,
            2,
            cv2.LINE_AA,
        )
        return annotated

    def _build_unique_path(self) -> Path:
        now = datetime.now()
        unique_suffix = f"{now.strftime('%Y%m%d_%H%M%S')}_{now.microsecond:06d}"
        filename = f"detection_{unique_suffix}.{self._image_format}"
        return self._image_directory / filename

    def cleanup_expired_images(self) -> List[Path]:
        """Remove imagens mais antigas que o período de retenção.

        Só arquivos com a extensão de imagem configurada são considerados;
        subdiretórios e arquivos não relacionados são ignorados. A falha ao
        remover um arquivo não interrompe a limpeza dos demais.

        Returns:
            A lista dos caminhos removidos com sucesso.
        """
        removed: List[Path] = []
        if not self._image_directory.is_dir():
            return removed

        now = time.time()
        suffix = f".{self._image_format}"

        for entry in self._image_directory.iterdir():
            if not entry.is_file() or entry.suffix.lower() != suffix:
                continue

            try:
                age_seconds = now - entry.stat().st_mtime
            except OSError:
                logger.exception("Error reading metadata for %s", entry)
                continue

            if age_seconds <= self._retention_seconds:
                continue

            try:
                entry.unlink()
            except OSError:
                logger.exception("Error removing expired image %s", entry)
                continue

            logger.info("Removed expired image %s", entry)
            removed.append(entry)

        return removed
