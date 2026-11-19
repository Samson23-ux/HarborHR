from uuid import UUID

import sentry_sdk
import sentry_sdk.logger as sentry_logger

from app.api.models.employee import EmployeePay as EmployeePayModel
from app.api.repo.employee_pay import EmployeePayRepository
from app.api.schemas.employee import EmployeePay as EmployeePaySchema
from app.core.exceptions import ServerError


class EmployeePayService:
    def __init__(self, employee_pay_repo: EmployeePayRepository):
        self._employee_pay_repo = employee_pay_repo

    async def _create_employee_pay(
        self,
        employee_id: UUID,
        organization_id: UUID,
        created_by: UUID,
        employee_pay: EmployeePaySchema,
        commit: bool = False,
    ) -> EmployeePayModel:
        try:
            pay_db = EmployeePayModel(
                employee_id=employee_id,
                organization_id=organization_id,
                created_by=created_by,
                **employee_pay.model_dump(),
            )
            pay_db = self._employee_pay_repo.add(model=pay_db)

            if commit:
                await self._employee_pay_repo.commit()
            else:
                await self._employee_pay_repo.flush()

            await self._employee_pay_repo.refresh(pay_db)

            return pay_db
        except Exception as exc:
            if commit:
                await self._employee_pay_repo.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while creating pay for employee {employee_id}",
                employee_id=employee_id,
            )
            raise ServerError() from exc
