"""Tests for app.config: no filesystem, network or webcam access."""

from pathlib import Path

import pytest

from app.config import ConfigError, load_config


def test_default_values_are_used_when_env_is_empty():
    config = load_config(env={})

    assert config.camera_index == 0
    assert config.camera_width == 1280
    assert config.camera_height == 720
    assert config.model_path == "yolo11n.pt"
    assert config.model_image_size == 480
    assert config.confidence_threshold == 0.65
    assert config.process_every_n_frames == 2
    assert config.detection_window_size == 5
    assert config.minimum_positive_frames == 3
    assert config.capture_cooldown_seconds == 0
    assert config.capture_delay_seconds == 0.5
    assert config.image_directory == Path("detections")
    assert config.image_format == "jpg"
    assert config.image_jpeg_quality == 90
    assert config.image_retention_hours == 24
    assert config.image_cleanup_interval_minutes == 30
    assert config.log_level == "INFO"


def test_numeric_values_are_converted_to_correct_types():
    env = {
        "CAMERA_INDEX": "1",
        "MODEL_IMAGE_SIZE": "640",
        "CONFIDENCE_THRESHOLD": "0.5",
        "CAPTURE_COOLDOWN_SECONDS": "30.5",
        "IMAGE_JPEG_QUALITY": "80",
    }

    config = load_config(env=env)

    assert config.camera_index == 1
    assert isinstance(config.camera_index, int)
    assert config.model_image_size == 640
    assert config.confidence_threshold == 0.5
    assert isinstance(config.confidence_threshold, float)
    assert config.capture_cooldown_seconds == 30.5
    assert config.image_jpeg_quality == 80


def test_invalid_integer_raises_config_error_with_clear_message():
    env = {"CAMERA_INDEX": "not-a-number"}

    with pytest.raises(ConfigError, match="CAMERA_INDEX"):
        load_config(env=env)


def test_invalid_float_raises_config_error_with_clear_message():
    env = {"CONFIDENCE_THRESHOLD": "abc"}

    with pytest.raises(ConfigError, match="CONFIDENCE_THRESHOLD"):
        load_config(env=env)


@pytest.mark.parametrize("value", ["-0.1", "1.1"])
def test_confidence_threshold_out_of_range_is_rejected(value):
    env = {"CONFIDENCE_THRESHOLD": value}

    with pytest.raises(ConfigError, match="CONFIDENCE_THRESHOLD"):
        load_config(env=env)


def test_detection_window_size_must_be_positive():
    env = {"DETECTION_WINDOW_SIZE": "0"}

    with pytest.raises(ConfigError, match="DETECTION_WINDOW_SIZE"):
        load_config(env=env)


def test_minimum_positive_frames_cannot_exceed_window_size():
    env = {"DETECTION_WINDOW_SIZE": "3", "MINIMUM_POSITIVE_FRAMES": "5"}

    with pytest.raises(ConfigError, match="MINIMUM_POSITIVE_FRAMES"):
        load_config(env=env)


def test_capture_cooldown_seconds_cannot_be_negative():
    env = {"CAPTURE_COOLDOWN_SECONDS": "-1"}

    with pytest.raises(ConfigError, match="CAPTURE_COOLDOWN_SECONDS"):
        load_config(env=env)


def test_capture_delay_seconds_cannot_be_negative():
    env = {"CAPTURE_DELAY_SECONDS": "-1"}

    with pytest.raises(ConfigError, match="CAPTURE_DELAY_SECONDS"):
        load_config(env=env)


@pytest.mark.parametrize("value", ["0", "101"])
def test_jpeg_quality_out_of_range_is_rejected(value):
    env = {"IMAGE_JPEG_QUALITY": value}

    with pytest.raises(ConfigError, match="IMAGE_JPEG_QUALITY"):
        load_config(env=env)


def test_process_every_n_frames_must_be_at_least_one():
    env = {"PROCESS_EVERY_N_FRAMES": "0"}

    with pytest.raises(ConfigError, match="PROCESS_EVERY_N_FRAMES"):
        load_config(env=env)


def test_retention_and_cleanup_periods_must_be_positive():
    with pytest.raises(ConfigError, match="IMAGE_RETENTION_HOURS"):
        load_config(env={"IMAGE_RETENTION_HOURS": "0"})

    with pytest.raises(ConfigError, match="IMAGE_CLEANUP_INTERVAL_MINUTES"):
        load_config(env={"IMAGE_CLEANUP_INTERVAL_MINUTES": "-5"})
