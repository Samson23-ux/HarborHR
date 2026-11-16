from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OrganizationBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class OrganizationInDB(OrganizationBase):
    id: UUID
    name: str
    country: str
    is_active: bool = True
