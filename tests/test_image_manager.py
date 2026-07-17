"""Tests for app.image_manager using temporary directories and synthetic frames."""

import os
import time

import numpy as np
import pytest

from app import image_manager as image_manager_module
from app.image_manager import ImageManager
from app.models import Detection


def make_frame() -> np.ndarray:
    return np.zeros((240, 320, 3), dtype=np.uint8)


def make_detection() -> Detection:
    return Detection(x1=10, y1=10, x2=100, y2=100, confidence=0.87, class_id=0, class_name="person")


def test_creates_directory_when_missing(tmp_path):
    target_dir = tmp_path / "does_not_exist_yet"
    assert not target_dir.exists()

    ImageManager(target_dir, image_format="jpg", jpeg_quality=90, retention_hours=24)

    assert target_dir.is_dir()


def test_generates_unique_filenames(tmp_path):
    manager = ImageManager(tmp_path, image_format="jpg", jpeg_quality=90, retention_hours=24)
    frame = make_frame()
    detections = [make_detection()]

    first_path = manager.save_detection_image(frame, detections)
    second_path = manager.save_detection_image(frame, detections)

    assert first_path is not None
    assert second_path is not None
    assert first_path != second_path


def test_saves_a_valid_image(tmp_path):
    manager = ImageManager(tmp_path, image_format="jpg", jpeg_quality=90, retention_hours=24)
    frame = make_frame()

    saved_path = manager.save_detection_image(frame, [make_detection()])

    assert saved_path is not None
    assert saved_path.exists()
    assert saved_path.stat().st_size > 0


def test_annotation_does_not_mutate_original_frame(tmp_path):
    manager = ImageManager(tmp_path, image_format="jpg", jpeg_quality=90, retention_hours=24)
    frame = make_frame()
    original = frame.copy()

    manager.save_detection_image(frame, [make_detection()])

    assert np.array_equal(frame, original)


def test_returns_correct_path(tmp_path):
    manager = ImageManager(tmp_path, image_format="jpg", jpeg_quality=90, retention_hours=24)
    frame = make_frame()

    saved_path = manager.save_detection_image(frame, [make_detection()])

    assert saved_path.parent == tmp_path
    assert saved_path.name.startswith("detection_")
    assert saved_path.suffix == ".jpg"


def test_cleanup_removes_expired_images(tmp_path):
    manager = ImageManager(tmp_path, image_format="jpg", jpeg_quality=90, retention_hours=1)

    old_file = tmp_path / "detection_old.jpg"
    old_file.write_bytes(b"fake-jpeg-content")
    old_time = time.time() - (2 * 3600)
    os.utime(old_file, (old_time, old_time))

    removed = manager.cleanup_expired_images()

    assert old_file in removed
    assert not old_file.exists()


def test_cleanup_keeps_images_within_retention_period(tmp_path):
    manager = ImageManager(tmp_path, image_format="jpg", jpeg_quality=90, retention_hours=24)

    recent_file = tmp_path / "detection_recent.jpg"
    recent_file.write_bytes(b"fake-jpeg-content")

    removed = manager.cleanup_expired_images()

    assert recent_file not in removed
    assert recent_file.exists()


def test_cleanup_ignores_non_image_files(tmp_path):
    manager = ImageManager(tmp_path, image_format="jpg", jpeg_quality=90, retention_hours=1)

    unrelated_file = tmp_path / "notes.txt"
    unrelated_file.write_text("keep me")
    old_time = time.time() - (2 * 3600)
    os.utime(unrelated_file, (old_time, old_time))

    removed = manager.cleanup_expired_images()

    assert unrelated_file not in removed
    assert unrelated_file.exists()


def test_handles_cv2_imwrite_failure(tmp_path, monkeypatch):
    manager = ImageManager(tmp_path, image_format="jpg", jpeg_quality=90, retention_hours=24)

    monkeypatch.setattr(image_manager_module.cv2, "imwrite", lambda *args, **kwargs: False)

    saved_path = manager.save_detection_image(make_frame(), [make_detection()])

    assert saved_path is None
