from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.core.enum import Role


class UserBase(BaseModel):
    id: UUID
    role_id: UUID
    employee_id: UUID | None = None
    organization_id: UUID | None = None
    is_active: bool = False
    is_verified: bool = False

    model_config = ConfigDict(from_attributes=True)


class GoogleUser(UserBase):
    google_id: str | None = None
    google_email: EmailStr | None = None


class EmailUser(UserBase):
    email: EmailStr | None = None


class UserInDB(GoogleUser, EmailUser):
    hashed_password: str | None = None


class BaseResponse(BaseModel):
    id: UUID
    role_id: UUID
    employee_id: UUID | None = None
    organization_id: UUID | None = None
    is_active: bool
    is_verified: bool
    updated_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserResponse(EmailUser, GoogleUser, BaseResponse):
    pass


class CachedUser(BaseModel):
    id: UUID
    role: Role
    email: EmailStr | None
    google_id: str | None
    google_email: EmailStr | None
    employee_id: UUID | None = None
    organization_id: UUID | None = None
    is_active: bool
    is_verified: bool
    updated_at: datetime | None
    created_at: datetime
