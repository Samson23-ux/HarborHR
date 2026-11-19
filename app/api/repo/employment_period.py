from typing import Any
from uuid import UUID

from sqlalchemy import desc, select

from app.api.models.employee import EmploymentPeriod as EmploymentPeriodModel
from app.api.repo.base import BaseRepository
from app.api.schemas.employee import EmploymentPeriod as EmploymentPeriodSchema


class EmploymentPeriodRepository(
    BaseRepository[EmploymentPeriodSchema, EmploymentPeriodModel]
):
    model = EmploymentPeriodModel

    SORT_FIELDS = ["start_date", "end_date", "created_at"]  # noqa: RUF012

    def _entity_to_model(self, entity: EmploymentPeriodSchema) -> EmploymentPeriodModel:
        return EmploymentPeriodModel(**entity.model_dump())

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
        if "start_date" in filters:
            filter_conditions.append(self.model.start_date == filters["start_date"])
        if "end_date" in filters:
            if filters["end_date"] is None:
                filter_conditions.append(self.model.end_date.is_(None))
            else:
                filter_conditions.append(self.model.end_date == filters["end_date"])

        return filter_conditions

    def _get_sort_fields(self, sort):
        sortable_fields = {
            "start_date": self.model.start_date,
            "end_date": self.model.end_date,
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

    async def get_latest_employment_period(
        self, employee_id: UUID, organization_id: UUID
    ) -> EmploymentPeriodModel | None:
        res = await self.async_session.execute(
            select(self.model)
            .where(
                self.model.employee_id == employee_id,
                self.model.organization_id == organization_id,
            )
            .order_by(desc(self.model.created_at), desc(self.model.id))
            .limit(1)
        )
        return res.scalar()
