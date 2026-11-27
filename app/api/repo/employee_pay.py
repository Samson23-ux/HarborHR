from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.api.models.employee import EmployeePay as EmployeePayModel
from app.api.repo.base import BaseRepository
from app.api.schemas.employee import EmployeePay as EmployeePaySchema


class EmployeePayRepository(BaseRepository[EmployeePaySchema, EmployeePayModel]):
    model = EmployeePayModel

    SORT_FIELDS = ["effective_from", "created_at"]  # noqa: RUF012

    def _entity_to_model(self, entity: EmployeePaySchema) -> EmployeePayModel:
        return EmployeePayModel(**entity.model_dump())

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
        if "version" in filters:
            filter_conditions.append(self.model.version == filters["version"])
        if "effective_from" in filters:
            filter_conditions.append(
                self.model.effective_from == filters["effective_from"]
            )

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
        return super()._parse_cursor_value(val)

    async def create_employee_pay(
        self, pay: EmployeePaySchema, **filters
    ) -> EmployeePayModel:
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
            .values(**pay.model_dump(), version=version)
            .on_conflict_do_nothing(index_elements=["employee_id", "effective_from"])
            .returning(self.model)
        )
        return result.scalar()
