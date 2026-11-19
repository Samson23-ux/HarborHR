from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from pydantic_extra_types.country import CountryAlpha3


class OrganizationBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)


class OrganizationInDB(OrganizationBase):
    id: UUID
    name: str
    country: str
    is_active: bool = True


class OrganizationUpdate(OrganizationBase):
    name: str | None = Field(default=None, max_length=128)
    country: CountryAlpha3 | None = None


class OrganizationResponse(OrganizationBase):
    id: UUID
    name: str
    country: str
    is_active: bool
    updated_at: datetime | None
    created_at: datetime
