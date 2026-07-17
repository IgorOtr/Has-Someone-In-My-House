"""Tests for web.image_encoder: local temp files only, no network."""

import base64

import pytest

from web.image_encoder import ImageEncodingError, encode_image_as_data_uri


def test_encodes_a_jpeg_file_as_a_data_uri(tmp_path):
    image_path = tmp_path / "detection_1.jpg"
    image_path.write_bytes(b"fake-jpeg-bytes")

    data_uri = encode_image_as_data_uri(image_path)

    assert data_uri.startswith("data:image/jpeg;base64,")


def test_encoded_content_decodes_back_to_the_original_bytes(tmp_path):
    original_bytes = b"\x89PNG\r\n\x1a\nfake-but-whatever"
    image_path = tmp_path / "detection_1.png"
    image_path.write_bytes(original_bytes)

    data_uri = encode_image_as_data_uri(image_path)

    encoded_part = data_uri.split(",", 1)[1]
    assert base64.b64decode(encoded_part) == original_bytes


def test_detects_png_mime_type(tmp_path):
    image_path = tmp_path / "detection_1.png"
    image_path.write_bytes(b"fake-png-bytes")

    data_uri = encode_image_as_data_uri(image_path)

    assert data_uri.startswith("data:image/png;base64,")


def test_falls_back_to_jpeg_mime_type_for_unknown_extension(tmp_path):
    image_path = tmp_path / "detection_1.unknownext"
    image_path.write_bytes(b"some-bytes")

    data_uri = encode_image_as_data_uri(image_path)

    assert data_uri.startswith("data:image/jpeg;base64,")


def test_accepts_a_string_path(tmp_path):
    image_path = tmp_path / "detection_1.jpg"
    image_path.write_bytes(b"fake-jpeg-bytes")

    data_uri = encode_image_as_data_uri(str(image_path))

    assert data_uri.startswith("data:image/jpeg;base64,")


def test_raises_for_a_missing_file(tmp_path):
    with pytest.raises(ImageEncodingError):
        encode_image_as_data_uri(tmp_path / "does-not-exist.jpg")
