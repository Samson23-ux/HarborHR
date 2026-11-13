import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    UUID,
    DateTime,
    Enum,
    PrimaryKeyConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.api.models.base import Base
from app.core.enum import Role


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, server_default=text("uuid_generate_v7()")
    )
    name: Mapped[Role] = mapped_column(
        Enum(Role, values_callable=lambda e: [m.value for m in e]), unique=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    __table_args__ = (PrimaryKeyConstraint("id", name="roles_pk"),)
