from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.api.models.statutory_rules import StatutoryRule
from app.api.repo.base import BaseRepository
from app.api.schemas.statutory_rules import (
    StatutoryRuleBase,
    StatutoryRuleInDB,
    StatutoryRuleListQuery,
)
from app.utils import is_valid_datetime


class StatutoryRuleRepository(BaseRepository[StatutoryRuleBase, StatutoryRule]):
    model = StatutoryRule

    SORT_FIELDS = ["effective_from", "created_at"]  # noqa: RUF012

    def _entity_to_model(self, entity: StatutoryRuleBase) -> StatutoryRule:
        return StatutoryRule(**entity.model_dump())

    def _get_filters(self, **filters) -> list[Any]:
        filter_conditions = []

        if "id" in filters:
            filter_conditions.append(self.model.id == filters["id"])
        if "version" in filters:
            filter_conditions.append(self.model.version == filters["version"])
        if "effective_from" in filters:
            filter_conditions.append(
                self.model.effective_from == filters["effective_from"]
            )
        if "created_by" in filters:
            filter_conditions.append(self.model.created_by == filters["created_by"])

        return filter_conditions

    def _get_sort_fields(self, sort):
        sortable_fields = {
            "effective_from": self.model.effective_from,
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
            val = is_valid_datetime(val)

        return is_valid, val

    async def get_statutory_rules(
        self, list_query: StatutoryRuleListQuery, **filters
    ) -> dict:
        filter_conditions = self._get_filters(**filters)
        stmt = select(self.model).where(*filter_conditions)

        return await self.sort_and_paginate(stmt, list_query)

    async def create_statutory_rule(
        self, rule: StatutoryRuleInDB, **filters
    ) -> StatutoryRule | None:
        filter_conditions = self._get_filters(**filters)

        await self.async_session.execute(
            select(self.model.id).where(*filter_conditions).with_for_update()
        )

        version = (
            select(func.coalesce(func.max(self.model.version), 0) + 1)
            .where(*filter_conditions)
            .scalar_subquery()
        )

        result = await self.async_session.execute(
            insert(self.model)
            .values(**rule.model_dump(), version=version)
            .on_conflict_do_nothing(index_elements=["version", "effective_from"])
            .returning(self.model)
        )
        return result.scalar()
