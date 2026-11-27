from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.api.models.user import User
from app.api.repo.base import BaseRepository
from app.api.schemas.user import UserBase
from app.utils import is_valid_datetime


class UserRepository(BaseRepository[UserBase, User]):
    model = User

    SORT_FIELDS = ["created_at", "updated_at"]  # noqa: RUF012

    @staticmethod
    def _entity_to_model(entity: UserBase) -> model:
        return User(**entity.model_dump())

    def _get_filters(self, **filters) -> list[Any]:
        filter_conditions = []

        if "id" in filters:
            filter_conditions.append(self.model.id == filters["id"])
        if "email" in filters:
            filter_conditions.append(self.model.email == filters["email"])
        if "google_email" in filters:
            filter_conditions.append(self.model.google_email == filters["google_email"])
        if "organization_id" in filters:
            filter_conditions.append(
                self.model.organization_id == filters["organization_id"],
            )
        if "is_active" in filters:
            filter_conditions.append(self.model.is_active.is_(filters["is_active"]))
        if "is_verified" in filters:
            filter_conditions.append(self.model.is_verified.is_(filters["is_verified"]))

        return filter_conditions

    def _select_in(
        self,
        stmt,
        with_role: bool = False,
    ):
        if with_role:
            stmt = stmt.options(selectinload(self.model.role))

        return stmt

    def _parse_cursor_value(self, val: Any) -> tuple[bool, Any]:
        is_valid = True

        if isinstance(val, str) and val.endswith("+00:00"):
            val = is_valid_datetime(val)

        return is_valid, val

    def _get_sort_fields(self, sort: str) -> tuple[list[str], Any, str]:
        sortable_fields: dict = {
            "created_at": self.model.created_at,
            "updated_at": self.model.updated_at,
        }

        column = sortable_fields.get(sort)

        if not column:
            sort_field = "created_at"
            column = self.model.created_at
        else:
            sort_field = sort

        return self.SORT_FIELDS, column, sort_field

    async def get_existing_user(
        self,
        email: str,
        *,
        is_active: bool | None = None,
        with_role: bool = False,
        with_lock: bool = False,
    ) -> User | None:
        stmt = select(self.model).where(
            or_(
                self.model.email == email,
                self.model.google_email == email,
            )
        )

        if is_active is not None:
            stmt = stmt.where(self.model.is_active.is_(is_active))

        if with_lock:
            stmt = stmt.with_for_update()

        stmt = self._select_in(stmt, with_role=with_role)

        res = await self.async_session.execute(stmt)
        return res.scalar()

    async def get_user_with_children(
        self, with_role: bool = False, **filters
    ) -> User | None:
        filter_conditions = self._get_filters(**filters)

        stmt = select(self.model).where(*filter_conditions)
        stmt = self._select_in(stmt, with_role)

        res = await self.async_session.execute(stmt)
        return res.scalar()
