from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    UUID,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.api.models.base import Base
from app.core.enum import UserType

if TYPE_CHECKING:
    from app.api.models.organization import Organization
    from app.api.models.role import Role

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, server_default=text("uuid_generate_v7()")
    )
    type: Mapped[UserType] = mapped_column(
        Enum(UserType, values_callable=lambda e: [m.value for m in e])
    )
    email: Mapped[str | None] = mapped_column(String, unique=True)
    hashed_password: Mapped[str | None] = mapped_column(String)
    google_id: Mapped[str | None] = mapped_column(String, unique=True)
    google_email: Mapped[str | None] = mapped_column(String, unique=True)
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        ForeignKey("roles.id", name="users_role_fk", ondelete="RESTRICT"),
    )
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID,
        ForeignKey("employees.id", name="users_employee_fk", ondelete="RESTRICT"),
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID,
        ForeignKey(
            "organizations.id", name="users_organization_fk", ondelete="RESTRICT"
        ),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    role: Mapped[Role] = relationship("Role", viewonly=True, lazy="selectin")
    organization: Mapped[Organization | None] = relationship(
        "Organization", viewonly=True, lazy="selectin"
    )

    __table_args__ = (
        PrimaryKeyConstraint("id", name="users_pk"),
        Index("idx_users_email", email),
        Index("idx_users_role_id", role_id),
        Index("idx_users_employee_id", employee_id),
        Index("idx_users_google_email", google_email),
        Index("idx_users_organization_id", organization_id),
    )
