from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.api.models.user import User
from app.api.schemas.invite import (
    InviteAccept,
    InviteCreate,
    InviteListQuery,
    InviteResponse,
    InviteState,
)
from app.api.schemas.response import AllSuccessResponse, SuccessResponse
from app.api.schemas.user import CachedUser
from app.core.enum import Role
from app.deps import InviteServiceDep, UnitOfWorkRepo, require_roles, write_limiter

router = APIRouter()


@router.get(
    "/invites",
    status_code=200,
    response_model=AllSuccessResponse[InviteResponse],
    description="Get all invites",
    dependencies=[write_limiter],
)
async def get_invites(
    request: Request,
    curr_user: Annotated[User | CachedUser, Depends(require_roles([Role.ADMIN]))],
    list_query: Annotated[InviteListQuery, Query()],
    invite_service: InviteServiceDep,
):
    invites_response, cursor = await invite_service.get_invites(curr_user, list_query)

    return AllSuccessResponse(
        message="Invites retrieved successfully",
        data=invites_response,
        cursor=cursor,
    )


@router.get(
    "/invites/{id}",
    status_code=200,
    response_model=SuccessResponse[InviteResponse],
    description="Get an invite",
    dependencies=[write_limiter],
)
async def get_invite(
    request: Request,
    id: UUID,
    curr_user: Annotated[User | CachedUser, Depends(require_roles([Role.ADMIN]))],
    invite_service: InviteServiceDep,
):
    invite = await invite_service.get_invite(curr_user, id)
    return SuccessResponse(message="Invite retrieved successfully", data=invite)


@router.post(
    "/invites",
    status_code=201,
    response_model=SuccessResponse[InviteResponse],
    description="Create an invite",
    dependencies=[write_limiter],
)
async def create_invite(
    request: Request,
    uow: UnitOfWorkRepo,
    curr_user: Annotated[User | CachedUser, Depends(require_roles([Role.ADMIN]))],
    invite_create: InviteCreate,
    invite_service: InviteServiceDep,
):
    invite = await invite_service.create_invite(curr_user, invite_create, uow)
    return SuccessResponse(message="Invite created successfully", data=invite)


@router.patch(
    "/invites/accept",
    status_code=200,
    response_model=SuccessResponse,
    description="Accept an invite",
    dependencies=[write_limiter],
)
async def accept_invite(
    request: Request,
    uow: UnitOfWorkRepo,
    invite_accept: InviteAccept,
    invite_service: InviteServiceDep,
):
    await invite_service.accept_invite(invite_accept, uow)
    return SuccessResponse(message="Invite accpted successfully")


@router.patch(
    "/invites/reject",
    status_code=200,
    response_model=SuccessResponse,
    description="Reject an invite",
    dependencies=[write_limiter],
)
async def reject_invite(
    request: Request,
    invite_state: InviteState,
    invite_service: InviteServiceDep,
):
    await invite_service.reject_invite(invite_state)
    return SuccessResponse(message="Invite rejected successfully")
