from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import AliasPath, BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.api.schemas.pagination import ListQuery
from app.core.enum import Role

SORT_FIELDS = Literal[
    "first_name",
    "-first_name",
    "last_name",
    "-last_name",
    "created_at",
    "-created_at",
    "updated_at",
    "-updated_at",
]


class Base(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True, from_attributes=True, populate_by_name=True
    )


class EmployeeListQuery(ListQuery):
    details: bool = False
    is_active: bool | None = None
    sort: SORT_FIELDS = "-created_at"


class EmployeeSearchQuery(EmployeeListQuery):
    q: str = Field(..., description="Search employees by first_name or last_name")


class EmploymentPeriod(Base):
    start_date: date
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_employment_period(self) -> Self:
        if self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class EmploymentPeriodUpdate(Base):
    end_date: date


class EmployeePay(Base):
    basic: Decimal = Field(..., max_digits=14, decimal_places=2)
    housing: Decimal = Field(..., max_digits=14, decimal_places=2)
    transport: Decimal = Field(..., max_digits=14, decimal_places=2)
    other_allowance: Decimal | None = Field(default=None, max_digits=14, decimal_places=2)
    other_deduction: Decimal | None = Field(default=None, max_digits=14, decimal_places=2)
    effective_from: date


class EmployeePayInDb(EmployeePay):
    employee_id: UUID
    organization_id: UUID
    created_by: UUID


class EmployeeBase(Base):
    first_name: str = Field(..., max_length=128)
    last_name: str = Field(..., max_length=128)
    organization_id: UUID
    email: EmailStr | None = None


class EmployeeCreate(EmployeeBase):
    user_id: UUID | None = None
    role: Role
    employment_period: EmploymentPeriod
    employee_pay: EmployeePay


class EmployeeUpdate(Base):
    first_name: str | None = None
    last_name: str | None = None


class EmployeeInDb(EmployeeBase):
    id: UUID
    role_id: UUID


# Response


class EmploymentPeriodResponse(Base):
    id: UUID
    employee_id: UUID
    organization_id: UUID
    start_date: date
    end_date: date | None = None
    created_at: datetime


class EmployeePayResponse(Base):
    id: UUID
    employee_id: UUID
    organization_id: UUID
    basic: Decimal
    housing: Decimal
    transport: Decimal
    other_allowance: Decimal | None = None
    other_deduction: Decimal | None = None
    version: int
    effective_from: date
    created_by: UUID
    created_at: datetime


class EmployeeResponse(Base):
    id: UUID
    first_name: str
    last_name: str
    email: EmailStr | None = None
    role: Role = Field(..., validation_alias=AliasPath("role", "name"))
    organization_id: UUID
    is_active: bool
    updated_at: datetime | None = None
    created_at: datetime


class EmployeeResponseWithDetails(EmployeeResponse):
    employment_period: list[EmploymentPeriodResponse]
    employee_pay: list[EmployeePayResponse]
