import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid7

import sentry_sdk
import sentry_sdk.logger as sentry_logger

from app.api.models.employee import Employee
from app.api.models.invite import Invite
from app.api.models.user import User
from app.api.repo.email import EmailRepository
from app.api.repo.employee import EmployeeRepository
from app.api.repo.invite import InviteRepository
from app.api.repo.redis import RedisRepository
from app.api.repo.uow import UnitOfWorkRepository
from app.api.repo.user import UserRepository
from app.api.schemas.invite import (
    InviteAccept,
    InviteCreate,
    InviteInDb,
    InviteListQuery,
    InviteResponse,
    InviteState,
)
from app.api.schemas.user import CachedUser
from app.api.services.email import EmailService
from app.api.services.employee import EmployeeService
from app.api.services.user import UserService
from app.core.config import get_settings
from app.core.enum import InviteStatus
from app.core.exceptions import (
    InviteExistsError,
    InviteExpiredError,
    InviteUserExistsError,
    NotFoundError,
    ServerError,
)
from app.core.security import Security

SETTINGS = get_settings()
INVITE_EMAIL_SUBJECT = "You've been invited to join HarborHR"


class InviteService:
    def __init__(
        self,
        security: Security,
        invite_repo: InviteRepository,
        redis_repo: RedisRepository,
    ):
        self._uow: UnitOfWorkRepository | None = None
        self._security = security
        self._invite_repo = invite_repo
        self._redis_repo = redis_repo

    async def _uow_invite_create(self, uow: UnitOfWorkRepository):
        self._uow = uow

        email_repo = self._uow.repo(EmailRepository)
        employee_repo = self._uow.repo(EmployeeRepository)
        self._invite_repo = self._uow.repo(InviteRepository)

        self._email_service = EmailService(email_repo=email_repo)
        self._employee_service = EmployeeService(
            employee_repo=employee_repo, redis_repo=self._redis_repo
        )

    async def _uow_invite_accept(self, uow: UnitOfWorkRepository):
        self._uow = uow

        user_repo = self._uow.repo(UserRepository)
        self._invite_repo = self._uow.repo(InviteRepository)

        self._user_service = UserService(
            user_repo=user_repo, redis_repo=self._redis_repo
        )

    def _hash_token(self, token: str):
        return self._security.hash_value_256(token, SETTINGS.INVITE_TOKEN_SECRET)

    async def _send_email(
        self,
        email_subject: str,
        recipient_email: str,
    ):
        payload: dict = {
            "email_subject": email_subject,
            "email_message": "",  # TODO: add email body function for invites
            "recipient_email": recipient_email,
        }

        await self._email_service.send_email(payload, recipient_email)

    async def get_invites(
        self, curr_user: User | CachedUser, list_query: InviteListQuery
    ) -> tuple[list[InviteResponse], str | None]:
        org_id: UUID = curr_user.organization_id
        await self._invite_repo.set_org_id_async(org_id)

        try:
            filters: dict = list_query.model_dump(
                exclude={"limit", "sort", "cursor"}, exclude_none=True
            )
            filters["organization_id"] = org_id

            records: dict = await self._invite_repo.get_invites(list_query, **filters)

            cursor, invites = records.get("cursor"), records.get("data")

            if not invites:
                sentry_logger.warning(
                    "Invites not found",
                    details={"org_id": org_id},
                )
                raise NotFoundError(entity="Invites")

            invites_response = []
            for invite in invites:
                invites_response.append(InviteResponse.model_validate(invite))

            sentry_logger.info("Invites retrieved", details={"org_id": org_id})

            return invites_response, cursor
        except NotFoundError:
            raise
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while retrieving invites",
                details={"org_id": org_id},
            )
            raise ServerError() from exc

    async def get_invite(
        self, curr_user: User | CachedUser, invite_id: UUID
    ) -> InviteResponse:
        org_id: UUID = curr_user.organization_id
        await self._invite_repo.set_org_id_async(org_id)

        try:
            invite: Invite | None = await self._invite_repo.get_record(
                id=invite_id, organization_id=org_id
            )

            if not invite:
                sentry_logger.warning(
                    "Invite not found with id {invite_id}",
                    invite_id=invite_id,
                    details={"org_id": org_id},
                )
                raise NotFoundError(entity="Invite")

            sentry_logger.info(
                "Invite {invite_id} retrieved",
                invite_id=invite_id,
                details={"org_id": org_id},
            )

            return InviteResponse.model_validate(invite)
        except NotFoundError:
            raise
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while retrieving invite {invite_id}",
                invite_id=invite_id,
                details={"org_id": org_id},
            )
            raise ServerError() from exc

    async def create_invite(
        self,
        curr_user: User | CachedUser,
        invite_create: InviteCreate,
        uow: UnitOfWorkRepository,
    ) -> InviteResponse:
        await self._uow_invite_create(uow)

        user_id: UUID = curr_user.id
        org_id: UUID = curr_user.organization_id

        await self._invite_repo.set_org_id_async(org_id)

        try:
            employee: Employee | None = await self._employee_service._get_employee(
                id=invite_create.employee_id,
                organization_id=org_id,
                is_active=True,
                email_exists=True,
            )

            if not employee:
                sentry_logger.warning(
                    "Employee not found with id {employee_id}",
                    employee_id=invite_create.employee_id,
                    details={"org_id": org_id},
                )
                raise NotFoundError(entity="Employee")

            token: str = secrets.token_urlsafe(32)
            invite_in_db: InviteInDb = InviteInDb(
                id=uuid7(),
                employee_id=invite_create.employee_id,
                organization_id=org_id,
                hashed_token=self._hash_token(token),
                created_by=user_id,
                expires_at=datetime.now(UTC) + timedelta(hours=SETTINGS.INVITE_EXPIRY),
            )

            invite: Invite | None = await self._invite_repo.create_invite(invite_in_db)

            if not invite:
                sentry_logger.warning(
                    "Invite already exists for employee {employee_id}",
                    employee_id=invite_create.employee_id,
                    details={"org_id": org_id},
                )

                raise InviteExistsError()

            await self._invite_repo.commit()

            await self._send_email(INVITE_EMAIL_SUBJECT, employee.email)
            return InviteResponse.model_validate(invite)
        except InviteExistsError, NotFoundError:
            raise
        except Exception as exc:
            await self._uow.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while creating invite", details={"error": str(exc)}
            )
            raise ServerError() from exc

    async def accept_invite(
        self, invite_accept: InviteAccept, uow: UnitOfWorkRepository
    ):
        await self._uow_invite_accept(uow)

        try:
            token: str = self._hash_token(invite_accept.token)
            invite: Invite | None = await self._invite_repo.get_invite(
                hashed_token=token, status=InviteStatus.ACTIVE
            )

            if not invite:
                sentry_logger.warning(
                    "Invite not found with token {token}",
                    token=token,
                )
                raise NotFoundError(entity="Invite")

            if datetime.now(UTC) >= invite.expires_at:
                sentry_logger.warning(
                    "Invite already expired. Token {token}",
                    token=token,
                )
                raise InviteExpiredError()

            hashed_password: str = await self._security.hash_password(
                invite_accept.password
            )
            await self._user_service.link_user(invite, hashed_password)

            invite.status = InviteStatus.USED
            invite.used_at = datetime.now(UTC)

            self._invite_repo.add(model=invite)
            await self._uow.commit()
        except NotFoundError, InviteUserExistsError, InviteExpiredError:
            raise
        except Exception as exc:
            await self._uow.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while accepting invite", details={"error": str(exc)}
            )
            raise ServerError() from exc

    async def reject_invite(self, invite_state: InviteState):
        try:
            token: str = self._hash_token(invite_state.token)
            invite: Invite | None = await self._invite_repo.get_record(
                hashed_token=token, status=InviteStatus.ACTIVE
            )

            if not invite:
                sentry_logger.warning(
                    "Invite not found with token {token}",
                    token=token,
                )
                raise NotFoundError(entity="Invite")

            if datetime.now(UTC) >= invite.expires_at:
                sentry_logger.warning(
                    "Invite already expired. Token {token}",
                    token=token,
                )
                raise InviteExpiredError()

            invite.status = InviteStatus.REJECTED
            invite.used_at = datetime.now(UTC)

            self._invite_repo.add(model=invite)
            await self._invite_repo.commit()
        except NotFoundError, InviteExpiredError:
            raise
        except Exception as exc:
            await self._uow.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while rejecting invite", details={"error": str(exc)}
            )
            raise ServerError() from exc
