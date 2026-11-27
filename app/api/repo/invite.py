from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.api.models.invite import Invite
from app.api.repo.base import BaseRepository
from app.api.schemas.invite import InviteInDb, InviteListQuery
from app.core.enum import InviteStatus


class InviteRepository(BaseRepository[InviteInDb, Invite]):
    model = Invite

    SORT_FIELDS = ["used_at", "expires_at", "created_at"]  # noqa: RUF012

    def _entity_to_model(self, entity: InviteInDb) -> Invite:
        return Invite(**entity.model_dump())

    def _get_filters(self, **filters) -> list[Any]:
        filter_conditions = []

        if "id" in filters:
            filter_conditions.append(self.model.id == filters["id"])
        if "employee_id" in filters:
            filter_conditions.append(self.model.employee_id == filters["employee_id"])
        if "organization_id" in filters:
            filter_conditions.append(
                self.model.organization_id == filters["organization_id"]
            )
        if "hashed_token" in filters:
            filter_conditions.append(self.model.hashed_token == filters["hashed_token"])
        if "status" in filters:
            filter_conditions.append(self.model.status == filters["status"])

        return filter_conditions

    def _get_sort_fields(self, sort):
        sortable_fields = {
            "used_at": self.model.used_at,
            "expires_at": self.model.expires_at,
            "created_at": self.model.created_at,
        }

        column = sortable_fields.get(sort)

        if not column:
            sort_field = "created_at"
            column = self.model.created_at
        else:
            sort_field = sort

        return self.SORT_FIELDS, column, sort_field

    def _parse_cursor_value(self, val):
        is_valid = True

        if isinstance(val, str) and val.endswith("+00:00"):
            try:
                val = datetime.fromisoformat(val)
            except ValueError, TypeError:
                is_valid = False

        return is_valid, val

    async def create_invite(self, invite: InviteInDb) -> Invite | None:
        stmt = (
            insert(self.model)
            .values(**invite.model_dump())
            .on_conflict_do_nothing(
                index_elements=["employee_id"],
                index_where=text(f"status = '{InviteStatus.ACTIVE.value}'"),
            )
            .returning(self.model)
        )

        res = await self.async_session.execute(stmt)
        return res.scalar()

    async def get_invite(self, **filters) -> Invite | None:
        filter_conditions = self._get_filters(**filters)
        stmt = (
            select(self.model)
            .where(*filter_conditions)
            .with_for_update()
            .options(selectinload(self.model.employee))
        )

        res = await self.async_session.execute(stmt)
        return res.scalar()

    async def get_invites(self, list_query: InviteListQuery, **filters) -> dict:
        filter_conditions = self._get_filters(**filters)

        stmt = select(self.model).where(*filter_conditions)
        return await self.sort_and_paginate(stmt, list_query)
