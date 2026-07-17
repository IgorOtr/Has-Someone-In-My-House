"""Structured data types shared across the application."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class Detection:
    """A single person detection produced by the detector."""

    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float
    class_id: int
    class_name: str


@dataclass(frozen=True)
class DetectionCapture:
    """Metadata describing a saved detection image."""

    image_path: Path
    detected_at: datetime
    highest_confidence: float
    person_count: int
