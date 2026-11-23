from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.pagination import ListQuery
from app.core.enum import InviteStatus

SORT_FIELDS = Literal[
    "used_at", "-used_at", "expires_at", "-expires_at", "created_at", "-created_at"
]


class InviteBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)


class InviteListQuery(ListQuery):
    sort: SORT_FIELDS = "-created_at"
    status: InviteStatus | None = None


class InviteCreate(InviteBase):
    employee_id: UUID


class InviteState(InviteBase):
    token: str


class InviteAccept(InviteState):
    password: str = Field(..., min_length=8, max_length=128)


class InviteInDb(InviteBase):
    id: UUID
    employee_id: UUID
    organization_id: UUID
    hashed_token: str
    created_by: UUID
    status: InviteStatus = InviteStatus.ACTIVE
    expires_at: datetime


class InviteResponse(InviteBase):
    id: UUID
    employee_id: UUID
    organization_id: UUID
    hashed_token: str
    created_by: UUID
    status: InviteStatus
    used_at: datetime | None
    expires_at: datetime
    created_at: datetime
