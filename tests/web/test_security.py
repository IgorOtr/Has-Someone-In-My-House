"""Tests for web.security: password hashing and JWT tokens, no I/O."""

import jwt
import pytest

from web.security import create_access_token, decode_access_token, hash_password, verify_password


def test_hash_password_produces_a_verifiable_hash():
    encoded = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", encoded) is True


def test_verify_password_rejects_wrong_password():
    encoded = hash_password("correct horse battery staple")

    assert verify_password("wrong password", encoded) is False


def test_hash_password_uses_a_random_salt_each_time():
    first = hash_password("same-password")
    second = hash_password("same-password")

    assert first != second
    assert verify_password("same-password", first) is True
    assert verify_password("same-password", second) is True


def test_verify_password_rejects_malformed_hash():
    assert verify_password("anything", "not-a-valid-hash") is False


def test_verify_password_rejects_unknown_algorithm():
    tampered = "bcrypt$12$somesalt$somehash"

    assert verify_password("anything", tampered) is False


def test_create_and_decode_access_token_roundtrip():
    token = create_access_token("user@example.com", secret_key="secret", expires_minutes=5)

    assert decode_access_token(token, secret_key="secret") == "user@example.com"


def test_decode_access_token_rejects_wrong_secret():
    token = create_access_token("user@example.com", secret_key="secret", expires_minutes=5)

    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token, secret_key="different-secret")


def test_decode_access_token_rejects_expired_token():
    token = create_access_token("user@example.com", secret_key="secret", expires_minutes=-1)

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token, secret_key="secret")
