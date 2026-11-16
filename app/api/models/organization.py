import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    UUID,
    VARCHAR,
    Boolean,
    DateTime,
    PrimaryKeyConstraint,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.api.models.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, server_default=text("uuid_generate_v7()")
    )
    name: Mapped[str] = mapped_column(String)
    country: Mapped[str] = mapped_column(VARCHAR(3))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (PrimaryKeyConstraint("id", name="organizations_pk"),)
