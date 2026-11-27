import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    UUID,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.api.models.base import Base


class StatutoryRule(Base):
    __tablename__ = "statutory_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, server_default=text("uuid_generate_v7()")
    )
    relief: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    relief_percentage: Mapped[Decimal] = mapped_column(Numeric(3))
    employee_pension_rate: Mapped[Decimal] = mapped_column(Numeric(3, 1))
    employer_pension_rate: Mapped[Decimal] = mapped_column(Numeric(3, 1))
    tax_bands: Mapped[dict] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer)
    
    effective_from: Mapped[date] = mapped_column(Date)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey(
            "users.id", name="statutory_rules_created_by_fk", ondelete="RESTRICT"
        ),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        PrimaryKeyConstraint("id", name="statutory_rules_pk"),
        UniqueConstraint("version", "effective_from", name="rules_version_from_unique"),
    )
