from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload

from app.api.models.employee import Employee
from app.api.repo.base import BaseRepository
from app.api.schemas.employee import Base as EmployeeBase
from app.api.schemas.employee import (
    EmployeeInDb,
    EmployeeListQuery,
    EmployeeSearchQuery,
)
from app.utils import is_valid_datetime


class EmployeeRepository(BaseRepository[EmployeeBase, Employee]):
    model = Employee

    SORT_FIELDS = ["first_name", "last_name", "created_at", "updated_at"]  # noqa: RUF012

    def _entity_to_model(self, entity):
        return Employee(**entity.model_dump())

    def _get_filters(self, **filters):
        filter_conditions = []

        if "id" in filters:
            filter_conditions.append(self.model.id == filters["id"])
        if "email" in filters:
            filter_conditions.append(self.model.email == filters["email"])
        if filters.get("is_active") is not None:
            filter_conditions.append(self.model.is_active.is_(filters["is_active"]))
        if "organization_id" in filters:
            filter_conditions.append(
                self.model.organization_id == filters["organization_id"]
            )
        if "email_exists" in filters:
            filter_conditions.append(self.model.email.is_not(None))

        return filter_conditions

    def _get_sort_fields(self, sort):
        sortable_fields = {
            "first_name": self.model.first_name,
            "last_name": self.model.last_name,
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

    def _parse_cursor_value(self, val):
        is_valid = True

        if isinstance(val, str) and val.endswith("+00:00"):
            val = is_valid_datetime(val)

        return is_valid, val

    async def create_employee(self, employee: EmployeeInDb) -> Employee | None:
        res = await self.async_session.execute(
            insert(self.model)
            .values(**employee.model_dump())
            .on_conflict_do_nothing(index_elements=["email"])
            .returning(self.model)
        )

        created = res.scalar()

        if not created:
            return None

        res = await self.async_session.execute(
            select(self.model)
            .where(self.model.id == created.id)
            .options(selectinload(self.model.role))
        )
        return res.scalar()

    async def get_employees(self, list_query: EmployeeListQuery, **filters) -> dict:
        filter_conditions = self._get_filters(**filters)
        stmt = (
            select(self.model)
            .where(*filter_conditions)
            .options(selectinload(self.model.role))
        )

        if list_query.details:
            stmt = stmt.options(
                selectinload(self.model.employment_periods),
                selectinload(self.model.employee_pay),
            )

        return await self.sort_and_paginate(stmt, list_query)

    async def get_employee(self, details: bool = False, **filters) -> Employee | None:
        filter_conditions = self._get_filters(**filters)

        stmt = (
            select(self.model)
            .where(*filter_conditions)
            .options(selectinload(self.model.role))
        )

        if details:
            stmt = stmt.options(
                selectinload(self.model.employment_periods),
                selectinload(self.model.employee_pay),
            )

        res = await self.async_session.execute(stmt)
        return res.scalar()

    async def search_employees(self, list_query: EmployeeSearchQuery, **filters):
        q = self._escape_search_param(list_query.q)
        filter_conditions = self._get_filters(**filters)

        stmt = (
            select(self.model)
            .where(
                *filter_conditions,
                or_(
                    self.model.first_name.ilike(q, escape=self.LIKE_ESCAPE),
                    self.model.last_name.ilike(q, escape=self.LIKE_ESCAPE),
                ),
            )
            .options(selectinload(self.model.role))
        )

        return await self.sort_and_paginate(stmt, list_query)
