from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    UUID,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.api.models.base import Base
from app.core.enum import InviteStatus

if TYPE_CHECKING:
    from app.api.models.employee import Employee


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, server_default=text("uuid_generate_v7()")
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("employees.id", name="invites_employee_fk", ondelete="RESTRICT"),
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey(
            "organizations.id", name="invites_organization_fk", ondelete="RESTRICT"
        ),
    )
    hashed_token: Mapped[str] = mapped_column(Text, unique=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("users.id", name="invites_created_by_fk", ondelete="RESTRICT"),
    )
    status: Mapped[InviteStatus] = mapped_column(
        Enum(InviteStatus, values_callable=lambda e: [m.value for m in e]),
        default=InviteStatus.ACTIVE,
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    employee: Mapped[Employee] = relationship("Employee", viewonly=True)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="invites_pk"),
        Index(
            "idx_invites_active",
            "employee_id",
            unique=True,
            postgresql_where=(status == InviteStatus.ACTIVE),
        ),
    )
