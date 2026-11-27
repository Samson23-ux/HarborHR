from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.schemas.pagination import ListQuery

SORT_FIELDS = Literal["created_at", "-created_at", "effective_from", "-effective_from"]


class StatutoryRuleBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)

    relief: Decimal = Field(..., max_digits=14, decimal_places=2)
    relief_percentage: Decimal = Field(..., max_digits=3)
    employee_pension_rate: Decimal = Field(..., max_digits=3, decimal_places=1)
    employer_pension_rate: Decimal = Field(..., max_digits=3, decimal_places=1)
    tax_bands: dict
    effective_from: date

    @field_validator("effective_from", mode="after")
    @classmethod
    def validate_effective_from(cls, v: date):
        if v < date.today():
            raise ValueError("effective_from cannot be before today")
        return v


class StatutoryRuleListQuery(ListQuery):
    sort: SORT_FIELDS = "-created_at"


class StatutoryRuleCreate(StatutoryRuleBase):
    pass


class StatutoryRuleInDB(StatutoryRuleCreate):
    created_by: UUID


class StatutoryRuleResponse(StatutoryRuleBase):
    id: UUID
    version: int
    created_by: UUID
    created_at: datetime
