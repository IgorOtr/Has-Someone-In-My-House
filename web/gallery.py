"""Acesso somente-leitura às imagens de detecção salvas, para o dashboard.

Este módulo nunca roda inferência nem toca a webcam; ele só lista, serve
e (opcionalmente) apaga arquivos que o monitor já salvou em
``IMAGE_DIRECTORY``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

_FILENAME_TIMESTAMP_PATTERN = re.compile(r"(\d{8})_(\d{6})_(\d{6})")


@dataclass(frozen=True)
class DetectionFile:
    filename: str
    detected_at: datetime
    size_bytes: int


class GalleryService:
    """Lista, serve e apaga imagens de detecção salvas."""

    def __init__(self, image_directory: Path, image_format: str) -> None:
        self._image_directory = Path(image_directory)
        self._suffix = f".{image_format.lower().lstrip('.')}"

    def list_detections(self, limit: int = 50, offset: int = 0) -> List[DetectionFile]:
        files = self._iter_image_files()
        files.sort(key=lambda item: item.detected_at, reverse=True)
        return files[offset : offset + limit]

    def count(self) -> int:
        return len(self._iter_image_files())

    def latest(self) -> Optional[DetectionFile]:
        files = self._iter_image_files()
        if not files:
            return None
        return max(files, key=lambda item: item.detected_at)

    def resolve_path(self, filename: str) -> Optional[Path]:
        """Retorna o caminho real de um arquivo, ou None se for inválido/inseguro."""
        if not self._is_valid_filename(filename):
            return None

        directory = self._image_directory.resolve()
        candidate = (directory / filename).resolve()
        if candidate.parent != directory:
            return None
        if not candidate.is_file():
            return None
        return candidate

    def delete(self, filename: str) -> bool:
        path = self.resolve_path(filename)
        if path is None:
            return False
        path.unlink()
        return True

    def _is_valid_filename(self, filename: str) -> bool:
        if not filename or "/" in filename or "\\" in filename:
            return False
        if filename in (".", ".."):
            return False
        return filename.lower().endswith(self._suffix)

    def _iter_image_files(self) -> List[DetectionFile]:
        if not self._image_directory.is_dir():
            return []

        results: List[DetectionFile] = []
        for entry in self._image_directory.iterdir():
            if not entry.is_file() or entry.suffix.lower() != self._suffix:
                continue
            try:
                stat = entry.stat()
            except OSError:
                continue
            results.append(
                DetectionFile(
                    filename=entry.name,
                    detected_at=self._parse_timestamp(entry.name, stat.st_mtime),
                    size_bytes=stat.st_size,
                )
            )
        return results

    @staticmethod
    def _parse_timestamp(filename: str, fallback_mtime: float) -> datetime:
        match = _FILENAME_TIMESTAMP_PATTERN.search(filename)
        if not match:
            return datetime.fromtimestamp(fallback_mtime)

        date_part, time_part, micros_part = match.groups()
        try:
            return datetime.strptime(f"{date_part}{time_part}{micros_part}", "%Y%m%d%H%M%S%f")
        except ValueError:
            return datetime.fromtimestamp(fallback_mtime)
