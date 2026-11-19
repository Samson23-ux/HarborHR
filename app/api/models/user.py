from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    UUID,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.api.models.base import Base

if TYPE_CHECKING:
    from app.api.models.role import Role


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, server_default=text("uuid_generate_v7()")
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

    role: Mapped[Role] = relationship("Role", viewonly=True)

    __table_args__ = (
        PrimaryKeyConstraint("id", name="users_pk"),
        CheckConstraint(
            """
                email IS NOT NULL AND hashed_password IS NOT NULL OR
                google_id IS NOT NULL AND google_email IS NOT NULL
            """,
            name="users_auth_ck",
        ),
        Index("idx_users_email", "email"),
        Index("idx_users_role_id", "role_id"),
        Index("idx_users_employee_id", "employee_id"),
        Index("idx_users_google_email", "google_email"),
        Index("idx_users_organization_id", "organization_id"),
    )
