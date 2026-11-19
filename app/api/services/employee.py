from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid7

import sentry_sdk
import sentry_sdk.logger as sentry_logger

from app.api.models.employee import Employee, EmployeePay, EmploymentPeriod
from app.api.models.user import User
from app.api.repo.employee import EmployeeRepository
from app.api.repo.employee_pay import EmployeePayRepository
from app.api.repo.employment_period import EmploymentPeriodRepository
from app.api.repo.uow import UnitOfWorkRepository
from app.api.repo.user import UserRepository
from app.api.schemas.employee import (
    EmployeeCreate,
    EmployeeInDb,
    EmployeeListQuery,
    EmployeePayInDb,
    EmployeePayResponse,
    EmployeeResponse,
    EmployeeResponseWithDetails,
    EmployeeUpdate,
    EmploymentPeriodResponse,
    EmploymentPeriodUpdate,
)
from app.api.schemas.employee import (
    EmployeePay as EmployeePaySchema,
)
from app.api.schemas.employee import (
    EmploymentPeriod as EmploymentPeriodSchema,
)
from app.api.schemas.user import CachedUser
from app.api.services.employee_pay import EmployeePayService
from app.api.services.employment_period import EmploymentPeriodService
from app.api.services.user import UserService
from app.core.exceptions import (
    ActiveEmploymentPeriodError,
    EntityExistsError,
    InvalidEmploymentPeriodError,
    NotFoundError,
    ServerError,
    UserLinkedError,
)


class EmployeeService:
    def __init__(self, employee_repo: EmployeeRepository):
        self._uow: UnitOfWorkRepository | None = None
        self._employee_repo = employee_repo

    async def _uow_employee_create(self, uow: UnitOfWorkRepository):
        self._uow = uow

        self._user_repo = await self._uow.repo(UserRepository)
        self._pay_repo = await self._uow.repo(EmployeePayRepository)
        self._period_repo = await self._uow.repo(EmploymentPeriodRepository)

        self._user_service = UserService(user_repo=self._user_repo)
        self._pay_service = EmployeePayService(employee_pay_repo=self._pay_repo)
        self._period_service = EmploymentPeriodService(
            employment_period_repo=self._period_repo
        )

    async def _set_current_org(self, org_id):
        await self._employee_repo.set_org_id_async(org_id)

    async def _link_employee_to_user(
        self, org_id: UUID, user_id: UUID, employee_id: UUID
    ):
        user: User | None = await self._user_service._get_user(
            with_role=True,
            id=user_id,
            is_verified=True,
            is_active=True,
            organization_id=org_id,
        )

        if not user:
            sentry_logger.warning(
                "User not found with id {user_id} for employee create", user_id=user
            )
            raise NotFoundError(entity="User")

        if user.employee_id:
            sentry_logger.warning("")
            raise UserLinkedError()

        user.employee_id = employee_id
        user.updated_at = datetime.now(UTC)

        await self._user_service.update_user(user)

        # TODO: Log employee create using celery task

    @staticmethod
    def _employee_response_with_details(
        employee: Employee,
        period: list[EmploymentPeriodResponse],
        pay: list[EmployeePayResponse],
    ):
        return EmployeeResponseWithDetails(
            id=employee.id,
            first_name=employee.first_name,
            last_name=employee.last_name,
            email=employee.email,
            organization_id=employee.organization_id,
            is_active=employee.is_active,
            updated_at=employee.updated_at,
            created_at=employee.created_at,
            employment_period=period,
            employee_pay=pay,
        )

    @staticmethod
    def _employment_period_response(
        employment_period: list[EmploymentPeriod],
    ) -> list[EmploymentPeriodResponse]:
        period_response = []

        for period in employment_period:
            period_response.append(EmploymentPeriodResponse.model_validate(period))
        return period_response

    @staticmethod
    def _employee_pay_response(
        employee_pay: list[EmployeePay],
    ) -> list[EmployeePayResponse]:
        pay_response = []

        for period in employee_pay:
            pay_response.append(EmployeePayResponse.model_validate(period))
        return pay_response

    async def _employee_with_details(
        self, curr_user: User, employee_id: UUID
    ) -> EmployeeResponseWithDetails:
        employee: Employee | None = await self._employee_repo.get_employee_with_details(
            employee_id=employee_id, org_id=curr_user.organization_id
        )

        if not employee:
            sentry_logger.warning(
                "Employee not found with id {employee_id}", employee_id=employee_id
            )
            raise NotFoundError(entity="Employee")

        return self._employee_response_with_details(
            employee,
            self._employment_period_response(employee.employment_periods),
            self._employee_pay_response(employee.employee_pay),
        )

    def _employees_response(
        self,
        employees: Sequence[Employee],
        organization_id: UUID,
        details: bool | None = None,
    ):
        employees_response = []

        if details:
            for employee in employees:
                employees_response.append(
                    self._employee_response_with_details(
                        employee,
                        self._employment_period_response(employee.employment_periods),
                        self._employee_pay_response(employee.employee_pay),
                    )
                )
        else:
            for employee in employees:
                employees_response.append(EmployeeResponse.model_validate(employee))

        sentry_logger.info(
            "Employees retrieved",
            details={"org_id": organization_id},
        )

    async def create_employee(
        self,
        curr_user: User | CachedUser,
        employee_create: EmployeeCreate,
        uow: UnitOfWorkRepository,
    ) -> EmployeeResponseWithDetails:
        await self._uow_employee_create(uow)
        await self._set_current_org(curr_user.organization_id)

        try:
            employee_id = uuid7()

            employee_in_db: EmployeeInDb = EmployeeInDb(
                id=employee_id,
                first_name=employee_create.first_name,
                last_name=employee_create.last_name,
                organization_id=employee_create.organization_id,
                email=employee_create.email,
            )
            employee: Employee | None = await self._employee_repo.create_employee(
                employee_in_db
            )

            if not employee:
                sentry_logger.warning(
                    "Employee already exists",
                    details={"org_id": curr_user.organization_id},
                )
                raise EntityExistsError(
                    entity="Employee",
                    entity_property="email",
                    entity_value=employee_create.email,
                )

            period: EmploymentPeriod = (
                await self._period_service._create_employment_period(
                    employee_id,
                    curr_user.organization_id,
                    EmploymentPeriod(**employee_create.employment_period.model_dump()),
                )
            )

            pay: EmployeePay = await self._pay_service._create_employee_pay(
                employee_id,
                curr_user.organization_id,
                curr_user.id,
                EmployeePay(**employee_create.employee_pay),
            )

            if employee_create.user_id:
                await self._link_employee_to_user(
                    curr_user.organization_id, employee_create.user_id, employee_id
                )

            employee_response: EmployeeResponseWithDetails = (
                self._employee_response_with_details(
                    employee,
                    self._employment_period_response([period]),
                    self._employee_pay_response([pay]),
                )
            )

            await self._uow.commit()

            # TODO: Log employee create using celery task

            sentry_logger.info(
                "Employee {employee_id} created by user {user_id}",
                user_id=curr_user.id,
                employee_id=employee_id,
                details={"org_id": curr_user.organization_id},
            )
            return employee_response
        except EntityExistsError, NotFoundError:
            raise
        except Exception as exc:
            await self._uow.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while creating employee",
                details={"org_id": curr_user.organization_id},
            )
            raise ServerError() from exc

    async def get_employees(
        self,
        curr_user: User | CachedUser,
        details: bool,
        list_query: EmployeeListQuery,
    ) -> tuple[list[EmployeeResponse | EmployeeResponseWithDetails], str]:
        await self._set_current_org(curr_user.organization_id)

        try:
            filters: dict = list_query.model_dump(exclude={"limit", "sort", "cursor"})
            filters["organization_id"] = curr_user.organization_id

            records: dict = await self._employee_repo.get_employees(
                details, list_query, **filters
            )

            cursor, employees = records.get("cursor"), records.get("data")

            if not employees:
                sentry_logger.warning(
                    "Employees not found",
                    details={"org_id": curr_user.organization_id},
                )
                raise NotFoundError(entity="Employees")

            return self._employees_response(
                employees, curr_user.organization_id, details
            ), cursor
        except NotFoundError:
            raise
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while retrieving employees",
                details={"org_id": curr_user.organization_id},
            )
            raise ServerError() from exc

    async def search_employees(
        self, curr_user: User | CachedUser, q: str, list_query: EmployeeListQuery
    ) -> tuple[list[EmployeeResponse | EmployeeResponseWithDetails], str]:
        await self._set_current_org(curr_user.organization_id)

        try:
            filters: dict = list_query.model_dump(exclude={"limit", "sort", "cursor"})
            filters["organization_id"] = curr_user.organization_id

            records: dict = await self._employee_repo.search_employees(
                q, list_query, **filters
            )

            cursor, employees = records.get("cursor"), records.get("data")

            if not employees:
                sentry_logger.warning(
                    "Employees not found",
                    details={"org_id": curr_user.organization_id},
                )
                raise NotFoundError(entity="Employees")

            return self._employees_response(
                employees, curr_user.organization_id
            ), cursor
        except NotFoundError:
            raise
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while searching employees",
                details={"org_id": curr_user.organization_id},
            )
            raise ServerError() from exc

    async def get_employee(
        self, curr_user: User | CachedUser, employee_id: UUID, details: bool
    ) -> EmployeeResponse | EmployeeResponseWithDetails:
        await self._set_current_org(curr_user.organization_id)

        try:
            if details:
                return await self._employee_with_details(curr_user, employee_id)

            employee: Employee | None = await self._employee_repo.get_record(
                id=employee_id,
                organization_id=curr_user.organization_id,
                is_active=True,
            )

            if not employee:
                sentry_logger.warning(
                    "Employee not found with id {employee_id}",
                    employee_id=employee_id,
                    details={"org_id": curr_user.organization_id},
                )
                raise NotFoundError(entity="Employee")

            sentry_logger.info(
                "Employee {employee_id} retrieved",
                employee_id=employee_id,
                details={"org_id": curr_user.organization_id},
            )
            return EmployeeResponse.model_validate(employee)
        except NotFoundError:
            raise
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while retrieving employee {employee_id}",
                employee_id=employee_id,
                details={"org_id": curr_user.organization_id},
            )
            raise ServerError() from exc

    async def update_employee(
        self,
        curr_user: User | CachedUser,
        employee_id: UUID,
        employee_update: EmployeeUpdate,
    ) -> EmployeeResponse:
        await self._set_current_org(curr_user.organization_id)

        try:
            employee: Employee | None = await self._employee_repo.get_record(
                id=employee_id,
                organization_id=curr_user.organization_id,
                is_active=True,
            )

            if not employee:
                sentry_logger.warning(
                    "Employee not found with id {employee_id}",
                    employee_id=employee_id,
                    details={"org_id": curr_user.organization_id},
                )
                raise NotFoundError(entity="Employee")

            update_fields: dict = employee_update.model_dump(exclude_none=True)
            for k, v in update_fields.items():
                setattr(employee, k, v)

            await self._employee_repo.commit()
            await self._employee_repo.refresh(employee)

            # TODO: Log employee create using celery task
            sentry_logger.info(
                "Employee {employee_id} updated",
                employee_id=employee_id,
                details={"org_id": curr_user.organization_id},
            )
            return EmployeeResponse.model_validate(employee)
        except NotFoundError:
            raise
        except Exception as exc:
            await self._uow.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while updating employee {employee_id}",
                employee_id=employee_id,
                details={"org_id": curr_user.organization_id},
            )
            raise ServerError() from exc

    async def create_employee_pay(
        self,
        curr_user: User | CachedUser,
        employee_id: UUID,
        employee_pay: EmployeePaySchema,
        uow: UnitOfWorkRepository,
    ) -> EmployeePayResponse:
        await self._set_current_org(curr_user.organization_id)
        pay_repo: EmployeePayRepository = uow.repo(EmployeePayRepository)

        try:
            pay_in_db = EmployeePayInDb(
                employee_id=employee_id,
                organization_id=curr_user.organization_id,
                created_by=curr_user.id,
                **employee_pay.model_dump(),
            )

            pay_db: EmployeePay = await pay_repo.create_employee_pay(
                pay_in_db,
                employee_id=employee_id,
                organization_id=curr_user.organization_id,
            )

            await pay_repo.commit()
            await pay_repo.refresh(pay_db)

            sentry_logger.info(
                "Pay for employee {employee_id} created",
                employee_id=employee_id,
                details={"org_id": curr_user.organization_id},
            )
            return EmployeePayResponse.model_validate(pay_db)
        except Exception as exc:
            await pay_repo.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while creating pay for employee {employee_id}",
                employee_id=employee_id,
                details={"org_id": curr_user.organization_id},
            )
            raise ServerError() from exc

    async def create_employment_period(
        self,
        curr_user: User | CachedUser,
        employee_id: UUID,
        employment_period: EmploymentPeriodSchema,
        uow: UnitOfWorkRepository,
    ) -> EmploymentPeriodResponse:
        await self._set_current_org(curr_user.organization_id)
        period_repo: EmploymentPeriodRepository = uow.repo(EmploymentPeriodRepository)

        try:
            latest_period: EmploymentPeriod | None = (
                await period_repo.get_latest_employment_period(
                    employee_id, curr_user.organization_id
                )
            )

            if latest_period and latest_period.end_date is None:
                sentry_logger.warning(
                    "Active employment period exists for employee {employee_id}",
                    employee_id=employee_id,
                    details={"org_id": curr_user.organization_id},
                )
                raise ActiveEmploymentPeriodError()

            if (
                latest_period
                and latest_period.end_date is not None
                and employment_period.start_date < latest_period.end_date
            ):
                sentry_logger.warning(
                    "New employment period overlaps the latest period for employee "
                    "{employee_id}",
                    employee_id=employee_id,
                    details={"org_id": curr_user.organization_id},
                )
                raise InvalidEmploymentPeriodError(
                    reason=(
                        "start_date must be on or after the latest employment "
                        "period's end_date"
                    )
                )

            period_db = EmploymentPeriod(
                employee_id=employee_id,
                organization_id=curr_user.organization_id,
                **employment_period.model_dump(),
            )
            period_db = period_repo.add(model=period_db)

            await period_repo.commit()
            await period_repo.refresh(period_db)

            sentry_logger.info(
                "Employment period for employee {employee_id} created",
                employee_id=employee_id,
                details={"org_id": curr_user.organization_id},
            )
            return EmploymentPeriodResponse.model_validate(period_db)
        except (ActiveEmploymentPeriodError, InvalidEmploymentPeriodError):
            raise
        except Exception as exc:
            await period_repo.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while creating employment period for employee "
                "{employee_id}",
                employee_id=employee_id,
                details={"org_id": curr_user.organization_id},
            )
            raise ServerError() from exc

    async def update_employment_period(
        self,
        curr_user: User | CachedUser,
        employee_id: UUID,
        employment_period_update: EmploymentPeriodUpdate,
        uow: UnitOfWorkRepository,
    ) -> EmploymentPeriodResponse:
        await self._set_current_org(curr_user.organization_id)
        period_repo: EmploymentPeriodRepository = uow.repo(EmploymentPeriodRepository)

        try:
            period: EmploymentPeriod | None = await period_repo.get_record(
                employee_id=employee_id,
                organization_id=curr_user.organization_id,
                end_date=None,
            )

            if not period:
                sentry_logger.warning(
                    "Active employment period not found for employee {employee_id}",
                    employee_id=employee_id,
                    details={"org_id": curr_user.organization_id},
                )
                raise NotFoundError(entity="EmploymentPeriod")

            if employment_period_update.end_date < period.start_date:
                sentry_logger.warning(
                    "Invalid employment period end_date for employee {employee_id}",
                    employee_id=employee_id,
                    details={"org_id": curr_user.organization_id},
                )
                raise InvalidEmploymentPeriodError()

            period.end_date = employment_period_update.end_date

            await period_repo.commit()
            await period_repo.refresh(period)

            # TODO: Log employee create using celery task
            sentry_logger.info(
                "Employment period for employee {employee_id} updated",
                employee_id=employee_id,
                details={"org_id": curr_user.organization_id},
            )
            return EmploymentPeriodResponse.model_validate(period)
        except (NotFoundError, InvalidEmploymentPeriodError):
            raise
        except Exception as exc:
            await period_repo.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while updating employment period for employee "
                "{employee_id}",
                employee_id=employee_id,
                details={"org_id": curr_user.organization_id},
            )
            raise ServerError() from exc

    async def deactivate_employee(
        self,
        curr_user: User | CachedUser,
        employee_id: UUID,
    ):
        await self._set_current_org(org_id=curr_user.organization_id)

        try:
            employee: Employee | None = await self._employee_repo.get_record(
                id=employee_id,
                organization_id=curr_user.organization_id,
                is_active=True,
            )

            if not employee:
                sentry_logger.warning(
                    "Employee not found with id {employee_id}",
                    employee_id=employee_id,
                    details={"org_id": curr_user.organization_id},
                )
                raise NotFoundError(entity="Employee")

            employee.is_active = False
            employee.updated_at = datetime.now(UTC)

            await self._employee_repo.commit()

            # TODO: Log employee create using celery task
            sentry_logger.info(
                "Employee {employee_id} deactivated",
                employee_id=employee_id,
                details={"org_id": curr_user.organization_id},
            )
        except NotFoundError:
            raise
        except Exception as exc:
            await self._uow.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while deactivating employee {employee_id}",
                employee_id=employee_id,
                details={"org_id": curr_user.organization_id},
            )
            raise ServerError() from exc

    async def reactivate_employee(
        self,
        curr_user: User | CachedUser,
        employee_id: UUID,
    ) -> EmployeeResponse:
        await self._set_current_org(curr_user.organization_id)

        try:
            employee: Employee | None = await self._employee_repo.get_record(
                id=employee_id,
                organization_id=curr_user.organization_id,
                is_active=False,
            )

            if not employee:
                sentry_logger.warning(
                    "Employee not found with id {employee_id}",
                    employee_id=employee_id,
                    details={"org_id": curr_user.organization_id},
                )
                raise NotFoundError(entity="Employee")

            employee.is_active = True
            employee.updated_at = datetime.now(UTC)

            await self._employee_repo.commit()
            await self._employee_repo.refresh(employee)

            # TODO: Log employee create using celery task
            sentry_logger.info(
                "Employee {employee_id} reactivated",
                employee_id=employee_id,
                details={"org_id": curr_user.organization_id},
            )
            return EmployeeResponse.model_validate(employee)
        except NotFoundError:
            raise
        except Exception as exc:
            await self._uow.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while reactivating employee {employee_id}",
                employee_id=employee_id,
                details={"org_id": curr_user.organization_id},
            )
            raise ServerError() from exc
