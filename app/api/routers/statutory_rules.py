from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.api.models.user import User
from app.api.schemas.response import AllSuccessResponse, SuccessResponse
from app.api.schemas.statutory_rules import (
    StatutoryRuleCreate,
    StatutoryRuleListQuery,
    StatutoryRuleResponse,
)
from app.api.schemas.user import CachedUser
from app.core.enum import Role
from app.deps import (
    StatutoryRuleServiceDep,
    read_limiter,
    require_roles,
    write_limiter,
)

router = APIRouter()


@router.get(
    "/statutory-rules",
    status_code=200,
    description="Get all statutory rules",
    response_model=AllSuccessResponse[StatutoryRuleResponse],
    dependencies=[read_limiter],
)
async def get_statutory_rules(
    request: Request,
    list_query: Annotated[StatutoryRuleListQuery, Query()],
    curr_user: Annotated[User | CachedUser, Depends(require_roles([Role.STAFF]))],
    statutory_rule_service: StatutoryRuleServiceDep,
):
    rules_response, cursor = await statutory_rule_service.get_statutory_rules(
        list_query
    )

    return AllSuccessResponse(
        message="Statutory rules retrieved successfully",
        data=rules_response,
        cursor=cursor,
    )


@router.get(
    "/statutory-rules/{id}",
    status_code=200,
    description="Get a statutory rule",
    response_model=SuccessResponse[StatutoryRuleResponse],
    dependencies=[read_limiter],
)
async def get_statutory_rule(
    request: Request,
    id: UUID,
    curr_user: Annotated[User | CachedUser, Depends(require_roles([Role.STAFF]))],
    statutory_rule_service: StatutoryRuleServiceDep,
):
    rule_response: StatutoryRuleResponse = (
        await statutory_rule_service.get_statutory_rule(id)
    )
    return SuccessResponse(
        message="Statutory rule retrieved successfully", data=rule_response
    )


@router.post(
    "/statutory-rules",
    status_code=201,
    description="Create a statutory rule",
    response_model=SuccessResponse[StatutoryRuleResponse],
    dependencies=[write_limiter],
)
async def create_statutory_rule(
    request: Request,
    statutory_rule: StatutoryRuleCreate,
    curr_user: Annotated[User | CachedUser, Depends(require_roles([Role.STAFF]))],
    statutory_rule_service: StatutoryRuleServiceDep,
):
    rule_response: StatutoryRuleResponse = (
        await statutory_rule_service.create_statutory_rule(curr_user, statutory_rule)
    )
    return SuccessResponse(
        message="Statutory rule created successfully", data=rule_response
    )
