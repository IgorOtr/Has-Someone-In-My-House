"""Tipos de dados estruturados compartilhados pela aplicação."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Detection:
    """Uma única detecção de pessoa produzida pelo detector."""

    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float
    class_id: int
    class_name: str


@dataclass(frozen=True)
class DetectionCapture:
    """Metadados descrevendo uma imagem de detecção salva."""

    image_path: Path
    detected_at: datetime
    highest_confidence: float
    person_count: int
