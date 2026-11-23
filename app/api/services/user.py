from uuid import UUID, uuid7

import sentry_sdk
import sentry_sdk.logger as sentry_logger

from app.api.models.invite import Invite
from app.api.models.user import User
from app.api.repo.redis import RedisRepository
from app.api.repo.user import UserRepository
from app.api.schemas.user import CachedUser, UserInDB
from app.core.config import get_settings
from app.core.exceptions import InviteUserExistsError, NotFoundError, ServerError
from app.serializers import _deserialize_cached_user, _serialize_user

SETTINGS = get_settings()


class UserService:
    def __init__(self, user_repo: UserRepository, redis_repo: RedisRepository):
        self._user_repo = user_repo
        self._redis_repo = redis_repo

    @staticmethod
    def _user_cache_key(user_id: UUID) -> str:
        return f"cache:user:{user_id!s}"

    async def get_user(self, with_role: bool = False, **filters) -> User:
        try:
            user: User | None = await self._user_repo.get_user_with_children(
                with_role=with_role, **filters
            )

            if not user:
                sentry_logger.warning(
                    "User not found with id {user_id}", user_id=filters.get("id")
                )
                raise NotFoundError(entity="User")

            return user
        except Exception as exc:
            if isinstance(exc, NotFoundError):
                raise NotFoundError(entity="User") from exc

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while retrieving user {user_id}",
                user_id=filters.get("id"),
            )
            raise ServerError() from exc

    async def _get_user(self, with_role: bool = False, **filters) -> User | None:
        return await self._user_repo.get_user_with_children(
            with_role=with_role, **filters
        )

    async def get_existing_user(
        self,
        email,
        *,
        is_active: bool | None = None,
        with_role: bool = False,
        with_lock: bool = False,
    ) -> User | None:
        return await self._user_repo.get_existing_user(
            email,
            is_active=is_active,
            with_role=with_role,
            with_lock=with_lock,
        )

    async def create_user(
        self, user: UserInDB, email: str, commit: bool = False
    ) -> User:
        try:
            user_db: User = self._user_repo.add(entity=user)

            if commit:
                await self._user_repo.commit()
                await self._user_repo.refresh(user_db)
            else:
                await self._user_repo.flush()
                await self._user_repo.refresh(user_db)

            return user_db
        except Exception as exc:
            if commit:
                await self._user_repo.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error("Error occurred while creating user")
            raise ServerError() from exc

    async def get_cached_user(self, **filters) -> CachedUser | None:
        cache_key: str = self._user_cache_key(filters.get("id"))
        cached: dict = await self._redis_repo.get_hset(cache_key)

        if cached:
            cached_user = _deserialize_cached_user(cached)

            if not cached_user.is_verified:
                sentry_logger.info(
                    "Cached user not found with id {user_id}", user_id=filters.get("id")
                )
                raise NotFoundError(entity="User")

            return cached_user

    async def cache_user(self, user: User):
        value: dict = _serialize_user(user)

        await self._redis_repo.create_hset(self._user_cache_key(user.id), value)

    async def invalidate_user_cache(self, user: User):
        await self._redis_repo.delete_key(self._user_cache_key(user.id))

    async def update_user(self, user: User, commit: bool = False) -> User:
        try:
            user = self._user_repo.add(model=user)

            if commit:
                await self._user_repo.commit()
                await self._user_repo.refresh(user)
            else:
                await self._user_repo.flush()
                await self._user_repo.refresh(user)

            await self.cache_user(user)
            return user
        except Exception as exc:
            if commit:
                await self._user_repo.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while updating user {user_id}", user_id=user.id
            )
            raise ServerError() from exc

    async def link_user(self, invite: Invite, hashed_password: str):
        existing_user: User | None = await self.get_existing_user(
            invite.employee.email, with_lock=True
        )

        if existing_user:
            sentry_logger.warning(
                "User {user_id} exists for the invited employee {employee_id}",
                user_id=existing_user.id,
                employee_id=invite.employee.id,
            )
            raise InviteUserExistsError()

        user: UserInDB = UserInDB(
            id=uuid7(),
            role_id=invite.employee.role_id,
            employee_id=invite.employee.id,
            organization_id=invite.organization_id,
            is_active=True,
            is_verified=True,
            email=invite.employee.email,
            hashed_password=hashed_password
        )

        self._user_repo.add(entity=user)
