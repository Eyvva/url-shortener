"""Тесты модуля безопасности (JWT, пароли)."""
import pytest
from datetime import timedelta

from app.core.security import (
    hash_password, verify_password, create_access_token, decode_token,
)


def test_hash_password_returns_string():
    hashed = hash_password("mypassword")
    assert isinstance(hashed, str)
    assert len(hashed) > 0


def test_hash_password_not_equal_to_plain():
    plain = "mypassword"
    hashed = hash_password(plain)
    assert hashed != plain


def test_verify_password_correct():
    plain = "correctpassword"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("correctpassword")
    assert verify_password("wrongpassword", hashed) is False


def test_hash_password_different_salts():
    hashed1 = hash_password("samepassword")
    hashed2 = hash_password("samepassword")
    assert hashed1 != hashed2


def test_verify_password_long_password():
    long_pass = "a" * 100
    hashed = hash_password(long_pass)
    assert verify_password(long_pass, hashed) is True



def test_create_and_decode_token():
    token = create_access_token({"sub": "42"})
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "42"


def test_decode_invalid_token():
    result = decode_token("invalid.token.here")
    assert result is None


def test_decode_empty_token():
    result = decode_token("")
    assert result is None


def test_token_contains_exp():
    token = create_access_token({"sub": "1"})
    payload = decode_token(token)
    assert "exp" in payload


def test_token_custom_expiry():
    token = create_access_token({"sub": "1"}, expires_delta=timedelta(hours=2))
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "1"


def test_token_with_extra_data():
    token = create_access_token({"sub": "1", "role": "admin"})
    payload = decode_token(token)
    assert payload["role"] == "admin"
