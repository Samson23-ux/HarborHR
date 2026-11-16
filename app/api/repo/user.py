from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select

from app.api.models.user import User
from app.api.repo.base import BaseRepository
from app.api.schemas.user import UserBase


class UserRepository(BaseRepository[UserBase, User]):
    model = User

    SORT_FIELDS = ["created_at"]  # noqa: RUF012

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
        if "is_active" in filters:
            filter_conditions.append(self.model.is_active.is_(filters["is_active"]))
        if "is_verified" in filters:
            filter_conditions.append(self.model.is_verified.is_(filters["is_verified"]))

        return filter_conditions

    def _email_or_google_user(self, email):
        return or_(
            and_(self.model.email.is_not(None), self.model.email == email),
            and_(
                self.model.google_email.is_not(None),
                self.model.google_email == email,
            ),
        )

    def _parse_cursor_value(self, val: Any) -> tuple[bool, Any]:
        is_valid = False

        if isinstance(val, str) and not is_valid:
            try:
                val = datetime.fromisoformat(val)
                is_valid = True
            except ValueError, TypeError:
                pass

        return is_valid, val

    def _get_sort_fields(self, sort: str) -> tuple[list[str], Any, str]:
        sortable_fields: dict = {"created_at": self.model.created_at}

        column = sortable_fields.get(sort)

        if not column:
            sort_field = "created_at"
            column = self.model.created_at
        else:
            sort_field = sort

        return self.SORT_FIELDS, column, sort_field

    async def get_existing_user(self, email: str) -> User | None:
        res = await self.async_session.execute(
            select(self.model).where(self._email_or_google_user(email))
        )

        return res.scalar()

    async def get_user_for_reactivation(self, email: str) -> User | None:
        res = await self.async_session.execute(
            select(self.model).where(
                self._email_or_google_user(email),
                self.model.is_active.is_(False),
            )
        )

        return res.scalar()
