from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.api.models.user import User
from app.api.schemas.organization import OrganizationResponse, OrganizationUpdate
from app.api.schemas.response import SuccessResponse
from app.api.schemas.user import CachedUser
from app.core.enum import Role
from app.deps import (
    CurrentActiveUser,
    OrganizationServiceDep,
    read_limiter,
    require_roles,
    write_limiter,
)

router = APIRouter()


@router.get(
    "/organization/{organization_id}",
    status_code=200,
    response_model=SuccessResponse[OrganizationResponse],
    description="Get an organization",
    dependencies=[read_limiter],
)
async def get_organization(
    request: Request,
    organization_id: UUID,
    curr_user: CurrentActiveUser,
    organization_service: OrganizationServiceDep,
):
    organization: OrganizationResponse = await organization_service.get_organization(
        curr_user, organization_id
    )
    return SuccessResponse(
        message="Organization retrieved successfully", data=organization
    )


@router.patch(
    "/organization/{organization_id}",
    status_code=200,
    response_model=SuccessResponse[OrganizationResponse],
    description="Update an organization",
    dependencies=[write_limiter],
)
async def update_organization(
    request: Request,
    organization_id: UUID,
    organization_update: OrganizationUpdate,
    curr_user: Annotated[User | CachedUser, Depends(require_roles([Role.ADMIN]))],
    organization_service: OrganizationServiceDep,
):
    organization: OrganizationResponse = await organization_service.update_organization(
        curr_user, organization_id, organization_update
    )
    return SuccessResponse(
        message="Organization updated successfully", data=organization
    )
