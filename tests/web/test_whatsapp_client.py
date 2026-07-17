"""Tests for web.whatsapp_client: httpx.post is mocked, no real network call."""

import base64

import httpx
import pytest

import web.whatsapp_client as whatsapp_client_module
from web.whatsapp_client import WhatsAppSendError, send_whatsapp_image
from web.whatsapp_config import WhatsAppConfig


def make_config():
    return WhatsAppConfig(
        instance_id="instance-123", token="token-456", client_token="client-token-789"
    )


def make_image(tmp_path, name="detection_1.jpg", content=b"fake-jpeg-content"):
    image_path = tmp_path / name
    image_path.write_bytes(content)
    return image_path


class FakeResponse:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


def test_send_whatsapp_image_succeeds_on_200(monkeypatch, tmp_path):
    image_path = make_image(tmp_path)
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse(200)

    monkeypatch.setattr(whatsapp_client_module.httpx, "post", fake_post)

    send_whatsapp_image(make_config(), "5524981402661", image_path, "Pessoa detectada")

    assert captured["url"] == (
        "https://api.z-api.io/instances/instance-123/token/token-456/send-image"
    )
    assert captured["json"]["phone"] == "5524981402661"
    assert captured["json"]["caption"] == "Pessoa detectada"
    assert captured["json"]["image"].startswith("data:image/jpeg;base64,")
    encoded_part = captured["json"]["image"].split(",", 1)[1]
    assert base64.b64decode(encoded_part) == b"fake-jpeg-content"
    assert captured["headers"]["Client-Token"] == "client-token-789"
    assert captured["headers"]["Content-Type"] == "application/json"


def test_send_whatsapp_image_sends_the_image_inline_not_a_local_path(monkeypatch, tmp_path):
    """Z-API's servers cannot read a path on the monitor's local filesystem,
    so the payload must carry the image data itself, not a bare path."""
    image_path = make_image(tmp_path)
    captured = {}
    monkeypatch.setattr(
        whatsapp_client_module.httpx,
        "post",
        lambda url, json, headers, timeout: (captured.update(json=json), FakeResponse(200))[1],
    )

    send_whatsapp_image(make_config(), "5524981402661", image_path, "Pessoa detectada")

    assert str(image_path) not in captured["json"]["image"]
    assert str(image_path.resolve()) not in captured["json"]["image"]


def test_send_whatsapp_image_raises_when_the_image_file_is_missing(tmp_path):
    with pytest.raises(WhatsAppSendError):
        send_whatsapp_image(
            make_config(),
            "5524981402661",
            tmp_path / "does-not-exist.jpg",
            "Pessoa detectada",
        )


def test_send_whatsapp_image_raises_on_non_200(monkeypatch, tmp_path):
    image_path = make_image(tmp_path)
    monkeypatch.setattr(
        whatsapp_client_module.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse(400, "Bad Request"),
    )

    with pytest.raises(WhatsAppSendError, match="400"):
        send_whatsapp_image(make_config(), "5524981402661", image_path, "Pessoa detectada")


def test_send_whatsapp_image_raises_on_network_error(monkeypatch, tmp_path):
    image_path = make_image(tmp_path)

    def raise_network_error(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(whatsapp_client_module.httpx, "post", raise_network_error)

    with pytest.raises(WhatsAppSendError):
        send_whatsapp_image(make_config(), "5524981402661", image_path, "Pessoa detectada")


def test_send_whatsapp_image_raises_on_timeout(monkeypatch, tmp_path):
    image_path = make_image(tmp_path)

    def raise_timeout(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(whatsapp_client_module.httpx, "post", raise_timeout)

    with pytest.raises(WhatsAppSendError):
        send_whatsapp_image(make_config(), "5524981402661", image_path, "Pessoa detectada")
