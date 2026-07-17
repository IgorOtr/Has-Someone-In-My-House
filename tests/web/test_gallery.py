"""Tests for web.gallery: no webcam, no model, only temporary directories."""

import os
import time
from datetime import datetime

from web.gallery import GalleryService


def touch(path, mtime=None):
    path.write_bytes(b"fake-jpeg-content")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def test_lists_no_detections_for_empty_directory(tmp_path):
    service = GalleryService(tmp_path, image_format="jpg")

    assert service.list_detections() == []
    assert service.count() == 0
    assert service.latest() is None


def test_parses_timestamp_from_filename():
    parsed = GalleryService._parse_timestamp(
        "detection_20260716_153000_123456.jpg", fallback_mtime=0
    )

    assert parsed == datetime(2026, 7, 16, 15, 30, 0, 123456)


def test_falls_back_to_mtime_when_filename_has_no_timestamp(tmp_path):
    service = GalleryService(tmp_path, image_format="jpg")
    mtime = time.time() - 3600
    touch(tmp_path / "not-a-detection.jpg", mtime=mtime)

    [item] = service.list_detections()

    assert item.detected_at == datetime.fromtimestamp(mtime)


def test_ignores_files_with_a_different_extension(tmp_path):
    service = GalleryService(tmp_path, image_format="jpg")
    touch(tmp_path / "detection_20260716_153000_123456.jpg")
    (tmp_path / "notes.txt").write_text("keep me")

    items = service.list_detections()

    assert len(items) == 1
    assert items[0].filename == "detection_20260716_153000_123456.jpg"


def test_list_detections_orders_newest_first(tmp_path):
    service = GalleryService(tmp_path, image_format="jpg")
    touch(tmp_path / "detection_20260716_100000_000000.jpg")
    touch(tmp_path / "detection_20260716_120000_000000.jpg")

    items = service.list_detections()

    assert [item.filename for item in items] == [
        "detection_20260716_120000_000000.jpg",
        "detection_20260716_100000_000000.jpg",
    ]


def test_count_and_latest(tmp_path):
    service = GalleryService(tmp_path, image_format="jpg")
    touch(tmp_path / "detection_20260716_100000_000000.jpg")
    touch(tmp_path / "detection_20260716_120000_000000.jpg")

    assert service.count() == 2
    assert service.latest().filename == "detection_20260716_120000_000000.jpg"


def test_resolve_path_returns_none_for_missing_file(tmp_path):
    service = GalleryService(tmp_path, image_format="jpg")

    assert service.resolve_path("missing.jpg") is None


def test_resolve_path_rejects_path_traversal(tmp_path):
    service = GalleryService(tmp_path, image_format="jpg")
    secret = tmp_path.parent / "secret.jpg"
    secret.write_bytes(b"top-secret")

    assert service.resolve_path("../secret.jpg") is None
    assert service.resolve_path("sub/dir.jpg") is None


def test_resolve_path_rejects_wrong_extension(tmp_path):
    service = GalleryService(tmp_path, image_format="jpg")
    touch(tmp_path / "detection.png")

    assert service.resolve_path("detection.png") is None


def test_delete_removes_file(tmp_path):
    service = GalleryService(tmp_path, image_format="jpg")
    touch(tmp_path / "detection_20260716_100000_000000.jpg")

    assert service.delete("detection_20260716_100000_000000.jpg") is True
    assert service.count() == 0


def test_delete_returns_false_for_unknown_file(tmp_path):
    service = GalleryService(tmp_path, image_format="jpg")

    assert service.delete("missing.jpg") is False
