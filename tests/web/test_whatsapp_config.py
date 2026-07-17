"""Tests for web.whatsapp_config: no network access."""

import pytest

from web.whatsapp_config import WhatsAppConfigError, load_whatsapp_config


def test_loads_all_values_from_env():
    config = load_whatsapp_config(
        env={
            "ZAPI_INSTANCE_ID": "instance-123",
            "ZAPI_TOKEN": "token-456",
            "ZAPI_CLIENT_TOKEN": "client-token-789",
        }
    )

    assert config.instance_id == "instance-123"
    assert config.token == "token-456"
    assert config.client_token == "client-token-789"


def test_send_image_url_is_built_correctly():
    config = load_whatsapp_config(
        env={
            "ZAPI_INSTANCE_ID": "instance-123",
            "ZAPI_TOKEN": "token-456",
            "ZAPI_CLIENT_TOKEN": "client-token-789",
        }
    )

    assert config.send_image_url == (
        "https://api.z-api.io/instances/instance-123/token/token-456/send-image"
    )


def test_missing_instance_id_raises():
    with pytest.raises(WhatsAppConfigError, match="ZAPI_INSTANCE_ID"):
        load_whatsapp_config(
            env={"ZAPI_TOKEN": "token-456", "ZAPI_CLIENT_TOKEN": "client-token-789"}
        )


def test_missing_token_raises():
    with pytest.raises(WhatsAppConfigError, match="ZAPI_TOKEN"):
        load_whatsapp_config(
            env={"ZAPI_INSTANCE_ID": "instance-123", "ZAPI_CLIENT_TOKEN": "client-token-789"}
        )


def test_missing_client_token_raises():
    with pytest.raises(WhatsAppConfigError, match="ZAPI_CLIENT_TOKEN"):
        load_whatsapp_config(env={"ZAPI_INSTANCE_ID": "instance-123", "ZAPI_TOKEN": "token-456"})


def test_blank_client_token_raises():
    with pytest.raises(WhatsAppConfigError, match="ZAPI_CLIENT_TOKEN"):
        load_whatsapp_config(
            env={
                "ZAPI_INSTANCE_ID": "instance-123",
                "ZAPI_TOKEN": "token-456",
                "ZAPI_CLIENT_TOKEN": "   ",
            }
        )


def test_empty_env_raises_for_all_missing():
    with pytest.raises(WhatsAppConfigError):
        load_whatsapp_config(env={})
