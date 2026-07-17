"""Carregamento e validação da configuração do monitor.

Lê a configuração exclusivamente de variáveis de ambiente (populadas a
partir de um arquivo ``.env`` via ``python-dotenv``, quando presente),
valida cada valor e converte para o tipo correto. Nenhum outro módulo do
monitor deve ler variáveis de ambiente diretamente.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from dotenv import load_dotenv
import os


class ConfigError(Exception):
    """Levantada quando um valor de configuração está ausente ou é inválido."""


@dataclass(frozen=True)
class AppConfig:
    camera_index: int
    camera_width: int
    camera_height: int

    model_path: str
    model_image_size: int
    confidence_threshold: float
    process_every_n_frames: int

    detection_window_size: int
    minimum_positive_frames: int

    capture_cooldown_seconds: float
    capture_delay_seconds: float

    image_directory: Path
    image_format: str
    image_jpeg_quality: int
    image_retention_hours: float
    image_cleanup_interval_minutes: float

    log_level: str


_DEFAULTS: Mapping[str, str] = {
    "CAMERA_INDEX": "0",
    "CAMERA_WIDTH": "1280",
    "CAMERA_HEIGHT": "720",
    "MODEL_PATH": "yolo11n.pt",
    "MODEL_IMAGE_SIZE": "480",
    "CONFIDENCE_THRESHOLD": "0.65",
    "PROCESS_EVERY_N_FRAMES": "2",
    "DETECTION_WINDOW_SIZE": "5",
    "MINIMUM_POSITIVE_FRAMES": "3",
    "CAPTURE_COOLDOWN_SECONDS": "0",
    "CAPTURE_DELAY_SECONDS": "0.5",
    "IMAGE_DIRECTORY": "detections",
    "IMAGE_FORMAT": "jpg",
    "IMAGE_JPEG_QUALITY": "90",
    "IMAGE_RETENTION_HOURS": "24",
    "IMAGE_CLEANUP_INTERVAL_MINUTES": "30",
    "LOG_LEVEL": "INFO",
}


def _get_raw(env: Mapping[str, str], key: str) -> str:
    value = env.get(key)
    if value is None or value.strip() == "":
        return _DEFAULTS[key]
    return value.strip()


def _get_int(env: Mapping[str, str], key: str) -> int:
    raw = _get_raw(env, key)
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(
            f"Invalid value for {key}: {raw!r} is not a valid integer."
        ) from exc


def _get_float(env: Mapping[str, str], key: str) -> float:
    raw = _get_raw(env, key)
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(
            f"Invalid value for {key}: {raw!r} is not a valid number."
        ) from exc


def _get_str(env: Mapping[str, str], key: str) -> str:
    return _get_raw(env, key)


def load_config(
    env: Optional[Mapping[str, str]] = None, dotenv_path: Optional[Path] = None
) -> AppConfig:
    """Carrega, converte e valida a configuração da aplicação.

    Args:
        env: Mapeamento opcional de onde ler os valores. Por padrão usa
            ``os.environ`` após carregar um arquivo ``.env`` (se existir).
            Esse parâmetro existe principalmente para tornar a função
            testável sem depender de variáveis de ambiente reais.
        dotenv_path: Caminho opcional e explícito para um arquivo ``.env``.

    Raises:
        ConfigError: Se algum valor de configuração estiver ausente,
            malformado ou falhar na validação.
    """
    if env is None:
        load_dotenv(dotenv_path=dotenv_path)
        env = os.environ

    camera_index = _get_int(env, "CAMERA_INDEX")
    camera_width = _get_int(env, "CAMERA_WIDTH")
    camera_height = _get_int(env, "CAMERA_HEIGHT")

    model_path = _get_str(env, "MODEL_PATH")
    model_image_size = _get_int(env, "MODEL_IMAGE_SIZE")
    confidence_threshold = _get_float(env, "CONFIDENCE_THRESHOLD")
    process_every_n_frames = _get_int(env, "PROCESS_EVERY_N_FRAMES")

    detection_window_size = _get_int(env, "DETECTION_WINDOW_SIZE")
    minimum_positive_frames = _get_int(env, "MINIMUM_POSITIVE_FRAMES")

    capture_cooldown_seconds = _get_float(env, "CAPTURE_COOLDOWN_SECONDS")
    capture_delay_seconds = _get_float(env, "CAPTURE_DELAY_SECONDS")

    image_directory = Path(_get_str(env, "IMAGE_DIRECTORY"))
    image_format = _get_str(env, "IMAGE_FORMAT").lower().lstrip(".")
    image_jpeg_quality = _get_int(env, "IMAGE_JPEG_QUALITY")
    image_retention_hours = _get_float(env, "IMAGE_RETENTION_HOURS")
    image_cleanup_interval_minutes = _get_float(env, "IMAGE_CLEANUP_INTERVAL_MINUTES")

    log_level = _get_str(env, "LOG_LEVEL").upper()

    if camera_index < 0:
        raise ConfigError("CAMERA_INDEX must be greater than or equal to 0.")
    if camera_width <= 0:
        raise ConfigError("CAMERA_WIDTH must be greater than 0.")
    if camera_height <= 0:
        raise ConfigError("CAMERA_HEIGHT must be greater than 0.")
    if model_image_size <= 0:
        raise ConfigError("MODEL_IMAGE_SIZE must be greater than 0.")
    if not 0.0 <= confidence_threshold <= 1.0:
        raise ConfigError("CONFIDENCE_THRESHOLD must be between 0 and 1.")
    if process_every_n_frames < 1:
        raise ConfigError("PROCESS_EVERY_N_FRAMES must be greater than or equal to 1.")
    if detection_window_size <= 0:
        raise ConfigError("DETECTION_WINDOW_SIZE must be greater than 0.")
    if minimum_positive_frames <= 0:
        raise ConfigError("MINIMUM_POSITIVE_FRAMES must be greater than 0.")
    if minimum_positive_frames > detection_window_size:
        raise ConfigError(
            "MINIMUM_POSITIVE_FRAMES cannot be greater than DETECTION_WINDOW_SIZE."
        )
    if capture_cooldown_seconds < 0:
        raise ConfigError("CAPTURE_COOLDOWN_SECONDS cannot be negative.")
    if capture_delay_seconds < 0:
        raise ConfigError("CAPTURE_DELAY_SECONDS cannot be negative.")
    if not 1 <= image_jpeg_quality <= 100:
        raise ConfigError("IMAGE_JPEG_QUALITY must be between 1 and 100.")
    if image_retention_hours <= 0:
        raise ConfigError("IMAGE_RETENTION_HOURS must be greater than 0.")
    if image_cleanup_interval_minutes <= 0:
        raise ConfigError("IMAGE_CLEANUP_INTERVAL_MINUTES must be greater than 0.")
    if not image_format:
        raise ConfigError("IMAGE_FORMAT cannot be empty.")

    return AppConfig(
        camera_index=camera_index,
        camera_width=camera_width,
        camera_height=camera_height,
        model_path=model_path,
        model_image_size=model_image_size,
        confidence_threshold=confidence_threshold,
        process_every_n_frames=process_every_n_frames,
        detection_window_size=detection_window_size,
        minimum_positive_frames=minimum_positive_frames,
        capture_cooldown_seconds=capture_cooldown_seconds,
        capture_delay_seconds=capture_delay_seconds,
        image_directory=image_directory,
        image_format=image_format,
        image_jpeg_quality=image_jpeg_quality,
        image_retention_hours=image_retention_hours,
        image_cleanup_interval_minutes=image_cleanup_interval_minutes,
        log_level=log_level,
    )
