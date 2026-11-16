from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.api.models.organization import Organization
from app.api.repo.base import BaseRepository
from app.api.schemas.organization import OrganizationBase


class OrganizationRepository(BaseRepository[OrganizationBase, Organization]):
    model = Organization

    def _entity_to_model(self, entity: OrganizationBase) -> Organization:
        return Organization(**entity.model_dump())

    def _get_filters(self, **filters) -> list[Any]:
        filter_conditions = []

        if "id" in filters:
            filter_conditions.append(self.model.id == filters["id"])
        if "name" in filters:
            filter_conditions.append(self.model.name == filters["name"])
        if "organization_code" in filters:
            filter_conditions.append(
                self.model.organization_code == filters["organization_code"]
            )
        if "is_active" in filters:
            filter_conditions.append(self.model.is_active.is_(filters["is_active"]))

        return filter_conditions

    def _get_sort_fields(self, sort):
        return super()._get_sort_fields(sort)

    def _parse_cursor_value(self, val):
        return super()._parse_cursor_value(val)

    async def select_record_id(self, **filters) -> UUID | None:
        filter_conditions: list[Any] = self._get_filters(**filters)

        res = await self.async_session.execute(
            select(self.model.id).where(*filter_conditions)
        )
        return res.scalar()
