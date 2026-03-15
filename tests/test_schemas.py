"""Тесты валидации Pydantic схем."""
import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.schemas.schemas import (
    LinkCreate, LinkUpdate, UserRegister, ProjectCreate, UnusedTTLUpdate,
)



def test_link_create_valid():
    link = LinkCreate(original_url="https://www.example.com")
    assert str(link.original_url) == "https://www.example.com"


def test_link_create_invalid_url():
    with pytest.raises(ValidationError):
        LinkCreate(original_url="not-a-url")


def test_link_create_ftp_url_invalid():
    with pytest.raises(ValidationError):
        LinkCreate(original_url="ftp://example.com")


def test_link_create_custom_alias_valid():
    link = LinkCreate(original_url="https://example.com", custom_alias="mylink")
    assert link.custom_alias == "mylink"


def test_link_create_alias_too_short():
    with pytest.raises(ValidationError):
        LinkCreate(original_url="https://example.com", custom_alias="ab")


def test_link_create_alias_too_long():
    with pytest.raises(ValidationError):
        LinkCreate(original_url="https://example.com", custom_alias="a" * 51)


def test_link_create_alias_invalid_chars():
    with pytest.raises(ValidationError):
        LinkCreate(original_url="https://example.com", custom_alias="my alias!")


def test_link_create_with_expiry():
    dt = datetime(2099, 12, 31, tzinfo=timezone.utc)
    link = LinkCreate(original_url="https://example.com", expires_at=dt)
    assert link.expires_at == dt


def test_link_create_no_alias():
    link = LinkCreate(original_url="https://example.com")
    assert link.custom_alias is None



def test_link_update_empty():
    update = LinkUpdate()
    assert update.original_url is None
    assert update.short_code is None


def test_link_update_invalid_url():
    with pytest.raises(ValidationError):
        LinkUpdate(original_url="not-a-url")


def test_link_update_valid_url():
    update = LinkUpdate(original_url="https://new.example.com")
    assert update.original_url == "https://new.example.com"



def test_user_register_valid():
    user = UserRegister(username="john", email="john@example.com", password="pass123")
    assert user.username == "john"


def test_user_register_username_too_short():
    with pytest.raises(ValidationError):
        UserRegister(username="ab", email="test@example.com", password="pass")


def test_user_register_username_too_long():
    with pytest.raises(ValidationError):
        UserRegister(username="a" * 51, email="test@example.com", password="pass")


def test_user_register_username_invalid_chars():
    with pytest.raises(ValidationError):
        UserRegister(username="john doe!", email="test@example.com", password="pass")


def test_user_register_username_with_underscore():
    user = UserRegister(username="john_doe", email="john@example.com", password="pass")
    assert user.username == "john_doe"



def test_project_create_valid():
    project = ProjectCreate(name="My Project", description="desc")
    assert project.name == "My Project"


def test_project_create_no_description():
    project = ProjectCreate(name="My Project")
    assert project.description is None



def test_unused_ttl_valid():
    ttl = UnusedTTLUpdate(days=30)
    assert ttl.days == 30


def test_unused_ttl_zero_invalid():
    with pytest.raises(ValidationError):
        UnusedTTLUpdate(days=0)


def test_unused_ttl_negative_invalid():
    with pytest.raises(ValidationError):
        UnusedTTLUpdate(days=-1)
