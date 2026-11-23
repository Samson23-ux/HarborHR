from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.api.models.user import User
from app.api.schemas.employee import (
    EmployeeCreate,
    EmployeeListQuery,
    EmployeePay,
    EmployeePayResponse,
    EmployeeResponse,
    EmployeeResponseWithDetails,
    EmployeeSearchQuery,
    EmployeeUpdate,
    EmploymentPeriod,
    EmploymentPeriodResponse,
    EmploymentPeriodUpdate,
)
from app.api.schemas.response import AllSuccessResponse, SuccessResponse
from app.api.schemas.user import CachedUser
from app.core.enum import Role
from app.deps import (
    EmployeeServiceDep,
    UnitOfWorkRepo,
    read_limiter,
    require_roles,
    write_limiter,
)

router = APIRouter()


@router.get(
    "/employees",
    status_code=200,
    description="Get all employees",
    response_model=AllSuccessResponse[EmployeeResponse | EmployeeResponseWithDetails],
    dependencies=[read_limiter],
)
async def get_employees(
    request: Request,
    list_query: Annotated[EmployeeListQuery, Query()],
    curr_user: Annotated[
        User | CachedUser, Depends(require_roles([Role.ADMIN, Role.PAYROLL_OFFICER]))
    ],
    employee_service: EmployeeServiceDep,
):
    employees_response, cursor = await employee_service.get_employees(
        curr_user, list_query
    )

    return AllSuccessResponse(
        message="Employees retrieved successfully",
        data=employees_response,
        cursor=cursor,
    )


@router.get(
    "/employees/search",
    status_code=200,
    description="Search for an employees",
    response_model=AllSuccessResponse[EmployeeResponse],
    dependencies=[read_limiter],
)
async def search_employees(
    request: Request,
    list_query: Annotated[EmployeeSearchQuery, Query()],
    curr_user: Annotated[
        User | CachedUser, Depends(require_roles([Role.ADMIN, Role.PAYROLL_OFFICER]))
    ],
    employee_service: EmployeeServiceDep,
):
    employees_response, cursor = await employee_service.search_employees(
        curr_user, list_query
    )

    return AllSuccessResponse(
        message="Employees retrieved successfully",
        data=employees_response,
        cursor=cursor,
    )


@router.get(
    "/employees/{id}",
    status_code=200,
    description="Get an employee",
    response_model=SuccessResponse[EmployeeResponse | EmployeeResponseWithDetails],
    dependencies=[read_limiter],
)
async def get_employee(
    request: Request,
    id: UUID,
    details: bool,
    curr_user: Annotated[
        User | CachedUser, Depends(require_roles([Role.ADMIN, Role.PAYROLL_OFFICER]))
    ],
    employee_service: EmployeeServiceDep,
):
    employee: (
        EmployeeResponse | EmployeeResponseWithDetails
    ) = await employee_service.get_employee(curr_user, id, details)

    return SuccessResponse(message="Employee retrieved successfully", data=employee)


@router.post(
    "/employees",
    status_code=201,
    description="Create an employee",
    response_model=SuccessResponse[EmployeeResponseWithDetails],
    dependencies=[write_limiter],
)
async def create_employee(
    request: Request,
    employee_create: EmployeeCreate,
    curr_user: Annotated[
        User | CachedUser, Depends(require_roles([Role.ADMIN, Role.PAYROLL_OFFICER]))
    ],
    employee_service: EmployeeServiceDep,
    uow: UnitOfWorkRepo,
):
    employee_response = await employee_service.create_employee(
        curr_user, employee_create, uow
    )
    return SuccessResponse(
        message="Employee created successfully", data=employee_response
    )


@router.patch(
    "/employees/{id}",
    status_code=200,
    description="Update an employee data",
    response_model=SuccessResponse[EmployeeResponse],
    dependencies=[write_limiter],
)
async def update_employee(
    request: Request,
    id: UUID,
    employee_update: EmployeeUpdate,
    curr_user: Annotated[
        User | CachedUser, Depends(require_roles([Role.ADMIN, Role.PAYROLL_OFFICER]))
    ],
    employee_service: EmployeeServiceDep,
):
    employee_response: EmployeeResponse = await employee_service.update_employee(
        curr_user, id, employee_update
    )
    return SuccessResponse(
        message="Employee updated successfully", data=employee_response
    )


@router.post(
    "/employees/{id}/pay",
    status_code=201,
    description="Create a pay record for an employee",
    response_model=SuccessResponse[EmployeePayResponse],
    dependencies=[write_limiter],
)
async def create_employee_pay(
    request: Request,
    id: UUID,
    employee_pay: EmployeePay,
    curr_user: Annotated[
        User | CachedUser, Depends(require_roles([Role.ADMIN, Role.PAYROLL_OFFICER]))
    ],
    employee_service: EmployeeServiceDep,
    uow: UnitOfWorkRepo,
):
    employee_pay_response: EmployeePayResponse = (
        await employee_service.create_employee_pay(curr_user, id, employee_pay, uow)
    )
    return SuccessResponse(
        message="Employee pay created successfully", data=employee_pay_response
    )


@router.post(
    "/employees/{id}/employment-period",
    status_code=201,
    description="Create an employment period for an employee",
    response_model=SuccessResponse[EmploymentPeriodResponse],
    dependencies=[write_limiter],
)
async def create_employment_period(
    request: Request,
    id: UUID,
    employment_period: EmploymentPeriod,
    curr_user: Annotated[
        User | CachedUser, Depends(require_roles([Role.ADMIN, Role.PAYROLL_OFFICER]))
    ],
    employee_service: EmployeeServiceDep,
    uow: UnitOfWorkRepo,
):
    employment_period_response: EmploymentPeriodResponse = (
        await employee_service.create_employment_period(
            curr_user, id, employment_period, uow
        )
    )
    return SuccessResponse(
        message="Employment period created successfully",
        data=employment_period_response,
    )


@router.patch(
    "/employees/{id}/employment-period",
    status_code=200,
    description="Update an employee's employment period end date",
    response_model=SuccessResponse[EmploymentPeriodResponse],
    dependencies=[write_limiter],
)
async def update_employment_period(
    request: Request,
    id: UUID,
    employment_period_update: EmploymentPeriodUpdate,
    curr_user: Annotated[
        User | CachedUser, Depends(require_roles([Role.ADMIN, Role.PAYROLL_OFFICER]))
    ],
    employee_service: EmployeeServiceDep,
    uow: UnitOfWorkRepo,
):
    employment_period: EmploymentPeriodResponse = (
        await employee_service.update_employment_period(
            curr_user, id, employment_period_update, uow
        )
    )
    return SuccessResponse(
        message="Employment period updated successfully", data=employment_period
    )


@router.patch(
    "/employees/{id}/reactivate",
    status_code=200,
    description="Reactivate an employee",
    response_model=SuccessResponse[EmployeeResponse],
    dependencies=[write_limiter],
)
async def reactivate_employee(
    request: Request,
    id: UUID,
    curr_user: Annotated[
        User | CachedUser, Depends(require_roles([Role.ADMIN, Role.PAYROLL_OFFICER]))
    ],
    employee_service: EmployeeServiceDep,
):
    employee_response: EmployeeResponse = await employee_service.reactivate_employee(
        curr_user, id
    )
    return SuccessResponse(
        message="Employee reactivated successfully", data=employee_response
    )


@router.delete(
    "/employees/{id}/deactivate",
    status_code=204,
    description="Deactivate an employee",
    dependencies=[write_limiter],
)
async def deactivate_employee(
    request: Request,
    id: UUID,
    curr_user: Annotated[
        User | CachedUser, Depends(require_roles([Role.ADMIN, Role.PAYROLL_OFFICER]))
    ],
    employee_service: EmployeeServiceDep,
):
    await employee_service.deactivate_employee(curr_user, id)
