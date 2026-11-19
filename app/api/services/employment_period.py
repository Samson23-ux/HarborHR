from uuid import UUID

import sentry_sdk
import sentry_sdk.logger as sentry_logger

from app.api.models.employee import EmploymentPeriod as EmploymentPeriodModel
from app.api.repo.employment_period import EmploymentPeriodRepository
from app.api.schemas.employee import EmploymentPeriod as EmploymentPeriodSchema
from app.core.exceptions import ServerError


class EmploymentPeriodService:
    def __init__(self, employment_period_repo: EmploymentPeriodRepository):
        self._employment_period_repo = employment_period_repo

    async def _create_employment_period(
        self,
        employee_id: UUID,
        organization_id: UUID,
        employment_period: EmploymentPeriodSchema,
        commit: bool = False,
    ) -> EmploymentPeriodModel:
        try:
            period_db = EmploymentPeriodModel(
                employee_id=employee_id,
                organization_id=organization_id,
                **employment_period.model_dump(),
            )
            period_db = self._employment_period_repo.add(model=period_db)

            if commit:
                await self._employment_period_repo.commit()
            else:
                await self._employment_period_repo.flush()

            await self._employment_period_repo.refresh(period_db)

            return period_db
        except Exception as exc:
            if commit:
                await self._employment_period_repo.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while creating employment period for employee "
                "{employee_id}",
                employee_id=employee_id,
            )
            raise ServerError() from exc
