"""Tests for web.auth_config: no filesystem, network or database access."""

import pytest

from web.auth_config import AuthConfigError, load_auth_config


def test_default_values_are_used_when_env_is_empty():
    config = load_auth_config(env={})

    assert config.db_host == "127.0.0.1"
    assert config.db_port == 3306
    assert config.db_user == "app_user"
    assert config.db_password == "app_password"
    assert config.db_name == "app_database"
    assert config.jwt_secret_key == "insecure-dev-secret-change-me"
    assert config.jwt_expires_minutes == 120
    assert config.uses_insecure_default_secret is True
    assert config.allow_public_registration is True


def test_database_url_includes_all_connection_parts():
    config = load_auth_config(
        env={
            "DB_HOST": "db.local",
            "DB_PORT": "3307",
            "DB_USER": "someuser",
            "DB_PASSWORD": "somepass",
            "DB_NAME": "somedb",
        }
    )

    assert config.database_url == "mysql+pymysql://someuser:somepass@db.local:3307/somedb?charset=utf8mb4"
    assert config.server_database_url == "mysql+pymysql://someuser:somepass@db.local:3307/"


def test_custom_secret_is_not_flagged_as_insecure():
    config = load_auth_config(env={"JWT_SECRET_KEY": "a-real-secret"})

    assert config.uses_insecure_default_secret is False


def test_invalid_db_port_raises():
    with pytest.raises(AuthConfigError, match="DB_PORT"):
        load_auth_config(env={"DB_PORT": "not-a-number"})


def test_db_port_must_be_positive():
    with pytest.raises(AuthConfigError, match="DB_PORT"):
        load_auth_config(env={"DB_PORT": "0"})


def test_db_name_rejects_special_characters():
    with pytest.raises(AuthConfigError, match="DB_NAME"):
        load_auth_config(env={"DB_NAME": "app; DROP TABLE users;"})


def test_jwt_expires_minutes_must_be_positive():
    with pytest.raises(AuthConfigError, match="JWT_EXPIRES_MINUTES"):
        load_auth_config(env={"JWT_EXPIRES_MINUTES": "0"})


@pytest.mark.parametrize("value", ["false", "False", "0", "no", "off"])
def test_allow_public_registration_accepts_falsey_values(value):
    config = load_auth_config(env={"ALLOW_PUBLIC_REGISTRATION": value})

    assert config.allow_public_registration is False


@pytest.mark.parametrize("value", ["true", "True", "1", "yes", "on"])
def test_allow_public_registration_accepts_truthy_values(value):
    config = load_auth_config(env={"ALLOW_PUBLIC_REGISTRATION": value})

    assert config.allow_public_registration is True


def test_allow_public_registration_rejects_invalid_value():
    with pytest.raises(AuthConfigError, match="ALLOW_PUBLIC_REGISTRATION"):
        load_auth_config(env={"ALLOW_PUBLIC_REGISTRATION": "maybe"})
