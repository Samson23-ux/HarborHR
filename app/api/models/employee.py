from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    UUID,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    literal_column,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.api.models.base import Base

if TYPE_CHECKING:
    from app.api.models.role import Role


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, server_default=text("uuid_generate_v7()")
    )
    first_name: Mapped[str] = mapped_column(String)
    last_name: Mapped[str] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String, unique=True)
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("roles.id", name="users_role_fk", ondelete="RESTRICT"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey(
            "organizations.id", name="employees_organization_fk", ondelete="RESTRICT"
        ),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        PrimaryKeyConstraint("id", name="employees_pk"),
        Index("idx_employees_org_id", "organization_id"),
        Index("idx_employees_is_active", "is_active"),
        Index(
            "idx_employees_first_name",
            "first_name",
            postgresql_using="gin",
            postgresql_ops={"first_name": "gin_trgm_ops"},
        ),
        Index(
            "idx_employees_last_name",
            "last_name",
            postgresql_using="gin",
            postgresql_ops={"last_name": "gin_trgm_ops"},
        ),
    )

    role: Mapped[Role] = relationship("Role", viewonly=True)
    employment_periods: Mapped[list[EmploymentPeriod]] = relationship(
        "EmploymentPeriod", viewonly=True
    )
    employee_pay: Mapped[list[EmployeePay]] = relationship("EmployeePay", viewonly=True)


class EmploymentPeriod(Base):
    __tablename__ = "employment_periods"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, server_default=text("uuid_generate_v7()")
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey(
            "employees.id", name="employment_period_employee_fk", ondelete="RESTRICT"
        ),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey(
            "organizations.id",
            name="employment_periods_organization_fk",
            ondelete="RESTRICT",
        ),
    )
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        PrimaryKeyConstraint("id", name="employment_periods_pk"),
        Index("idx_employment_periods_org_id", "organization_id"),
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date", name="ck_employment_period"
        ),
        ExcludeConstraint(
            ("employee_id", "="),
            (
                literal_column("daterange(start_date, end_date, '[)')"),
                "&&",
            ),
            using="gist",
            name="employment_period_ex",
        ),
    )


class EmployeePay(Base):
    __tablename__ = "employee_pay"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, server_default=text("uuid_generate_v7()")
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey(
            "employees.id", name="employee_pay_employee_fk", ondelete="RESTRICT"
        ),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey(
            "organizations.id", name="employee_pay_organization_fk", ondelete="RESTRICT"
        ),
    )
    basic: Mapped[Decimal] = mapped_column(Numeric(precision=14, scale=2))
    housing: Mapped[Decimal] = mapped_column(Numeric(precision=14, scale=2))
    transport: Mapped[Decimal] = mapped_column(Numeric(precision=14, scale=2))
    other_allowance: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=14, scale=2)
    )
    other_deduction: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=14, scale=2)
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    effective_from: Mapped[date] = mapped_column(Date)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("users.id", name="employee_pay_created_by_fk", ondelete="RESTRICT"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        PrimaryKeyConstraint("id", name="employee_pay_pk"),
        Index("idx_employee_pay_org_id", "organization_id"),
        UniqueConstraint("employee_id", "version", name="pay_version_unique"),
        UniqueConstraint(
            "employee_id", "effective_from", name="pay_effective_from_unique"
        ),
    )


class EmployeeLog(Base):
    __tablename__ = "employee_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, server_default=text("uuid_generate_v7()")
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey(
            "employees.id", name="employee_log_employee_fk", ondelete="RESTRICT"
        ),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey(
            "organizations.id", name="employee_log_organization_fk", ondelete="RESTRICT"
        ),
    )
    previous_values: Mapped[dict | None] = mapped_column(JSONB)
    current_values: Mapped[dict] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(String)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("users.id", name="employee_log_created_by_fk", ondelete="RESTRICT"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (PrimaryKeyConstraint("id", name="employee_log_pk"),)
