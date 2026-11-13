from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.api.models.user import UserType


class UserBase(BaseModel):
    id: UUID
    type: UserType
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


class UserResponse(BaseModel):
    created_at: datetime


class GoogleUserResponse(GoogleUser, UserResponse):
    pass


class EmailUserResponse(EmailUser, UserResponse):
    pass
