from uuid import UUID

import sentry_sdk
import sentry_sdk.logger as sentry_logger

from app.api.models.organization import Organization
from app.api.repo.organization import OrganizationRepository
from app.api.schemas.organization import OrganizationInDB
from app.core.exceptions import NotFoundError, ServerError


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
