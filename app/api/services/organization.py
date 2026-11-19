from datetime import UTC, datetime
from uuid import UUID

import sentry_sdk
import sentry_sdk.logger as sentry_logger

from app.api.models.organization import Organization
from app.api.models.user import User
from app.api.repo.organization import OrganizationRepository
from app.api.schemas.organization import (
    OrganizationInDB,
    OrganizationResponse,
    OrganizationUpdate,
)
from app.core.exceptions import (
    AuthorizationError,
    ErrorCode,
    NotFoundError,
    ServerError,
)


class OrganizationService:
    def __init__(self, organization_repo: OrganizationRepository):
        self._organization_repo = organization_repo

    async def create_organization(
        self, organization: OrganizationInDB, commit: bool = False
    ) -> Organization:
        try:
            organization_db: Organization = self._organization_repo.add(
                entity=organization
            )

            if commit:
                await self._organization_repo.commit()
                await self._organization_repo.refresh(organization_db)
            else:
                await self._organization_repo.flush()
                await self._organization_repo.refresh(organization_db)

            return organization_db
        except Exception as exc:
            if commit:
                await self._organization_repo.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error("Error occurred while creating organization")
            raise ServerError() from exc

    async def select_organization_id(self, **filters) -> UUID:
        try:
            organization_id: UUID | None = (
                await self._organization_repo.select_record_id(**filters)
            )

            if not organization_id:
                sentry_logger.warning("Organization not found")
                raise NotFoundError(entity="Organization")

            return organization_id
        except NotFoundError:
            raise
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error("Error occurred while selecting organization")
            raise ServerError() from exc

    @staticmethod
    def _authorize_organization_access(curr_user: User, organization_id: UUID):
        if curr_user.organization_id != organization_id:
            sentry_logger.warning(
                "User {user_id} attempted to access organization {organization_id}",
                user_id=curr_user.id,
                organization_id=organization_id,
            )
            raise AuthorizationError(
                code=ErrorCode.NOT_PERMITTED,
                details={"reason": "Organization access denied"},
            )

    async def get_organization(
        self, curr_user: User, organization_id: UUID
    ) -> OrganizationResponse:
        try:
            self._authorize_organization_access(curr_user, organization_id)
            await self._organization_repo.set_org_id_async(curr_user.organization_id)

            organization: Organization | None = (
                await self._organization_repo.get_record(id=organization_id)
            )

            if not organization:
                sentry_logger.warning(
                    "Organization {organization_id} not found",
                    organization_id=organization_id,
                )
                raise NotFoundError(entity="Organization")

            return OrganizationResponse.model_validate(organization)
        except (NotFoundError, AuthorizationError):
            raise
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while retrieving organization {organization_id}",
                organization_id=organization_id,
            )
            raise ServerError() from exc

    async def update_organization(
        self,
        curr_user: User,
        organization_id: UUID,
        organization_update: OrganizationUpdate,
    ) -> OrganizationResponse:
        try:
            self._authorize_organization_access(curr_user, organization_id)
            await self._organization_repo.set_org_id_async(curr_user.organization_id)

            organization: Organization | None = (
                await self._organization_repo.get_record(id=organization_id)
            )

            if not organization:
                sentry_logger.warning(
                    "Organization {organization_id} not found",
                    organization_id=organization_id,
                )
                raise NotFoundError(entity="Organization")

            fields_to_update: dict = organization_update.model_dump(
                exclude_unset=True, exclude_none=True
            )

            if fields_to_update:
                for field, value in fields_to_update.items():
                    setattr(organization, field, value)

                organization.updated_at = datetime.now(UTC)

                organization = self._organization_repo.add(model=organization)
                await self._organization_repo.commit()
                await self._organization_repo.refresh(organization)

                sentry_logger.info(
                    "Organization {organization_id} updated",
                    organization_id=organization.id,
                )

            return OrganizationResponse.model_validate(organization)
        except (NotFoundError, AuthorizationError):
            raise
        except Exception as exc:
            await self._organization_repo.rollback()
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while updating organization {organization_id}",
                organization_id=organization_id,
            )
            raise ServerError() from exc
