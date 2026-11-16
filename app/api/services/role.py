from uuid import UUID

import sentry_sdk
import sentry_sdk.logger as sentry_logger

from app.api.repo.role import RoleRepository
from app.core.exceptions import ServerError


class RoleService:
    def __init__(self, role_repo: RoleRepository):
        self._role_repo = role_repo

    async def select_role_id(self, **filters) -> UUID | None:
        try:
            return await self._role_repo.select_record_id(**filters)
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while selecting role {role_name}",
                role_name=filters.get("name"),
            )
            raise ServerError() from exc
