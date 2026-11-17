from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.passwords import MAX_PASSWORD_LEN, MIN_PASSWORD_LEN
from app.models.enums import Role


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str
    role: Role


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    role: Role
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=MIN_PASSWORD_LEN, max_length=MAX_PASSWORD_LEN)
    role: Role = Role.OPERATOR


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Optional[Role] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=MIN_PASSWORD_LEN, max_length=MAX_PASSWORD_LEN)


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    old_password: str = Field(max_length=MAX_PASSWORD_LEN)
    new_password: str = Field(min_length=MIN_PASSWORD_LEN, max_length=MAX_PASSWORD_LEN)
