from __future__ import annotations
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, HttpUrl, field_validator, model_validator



class UserRegister(BaseModel):
    username: str
    email: str
    password: str

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username must be alphanumeric (underscores/hyphens allowed)")
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Username must be 3–50 characters")
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut




class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: Optional[int]
    created_at: datetime
    link_count: int = 0

    model_config = {"from_attributes": True}




class LinkCreate(BaseModel):
    original_url: str
    custom_alias: Optional[str] = None
    expires_at: Optional[datetime] = None
    project_id: Optional[int] = None

    @field_validator("original_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("custom_alias")
    @classmethod
    def validate_alias(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Alias must be alphanumeric (underscores/hyphens allowed)")
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Alias must be 3–50 characters")
        return v


class LinkUpdate(BaseModel):
    original_url: Optional[str] = None
    short_code: Optional[str] = None
    expires_at: Optional[datetime] = None
    project_id: Optional[int] = None

    @field_validator("original_url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class LinkOut(BaseModel):
    id: int
    short_code: str
    original_url: str
    short_url: str = ""
    owner_id: Optional[int]
    project_id: Optional[int]
    click_count: int
    created_at: datetime
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    is_active: bool

    model_config = {"from_attributes": True}


class LinkStats(BaseModel):
    short_code: str
    original_url: str
    short_url: str
    click_count: int
    created_at: datetime
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    owner_id: Optional[int]
    project_id: Optional[int]

    model_config = {"from_attributes": True}


class ExpiredLinkOut(BaseModel):
    short_code: str
    original_url: str
    click_count: int
    created_at: datetime
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    deleted_at: Optional[datetime]

    model_config = {"from_attributes": True}



class UnusedTTLUpdate(BaseModel):
    days: int

    @field_validator("days")
    @classmethod
    def positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Days must be >= 1")
        return v


class MessageOut(BaseModel):
    message: str
