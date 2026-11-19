from typing import Annotated

import sentry_sdk.logger as sentry_logger
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models.user import User
from app.api.repo.email import EmailRepository
from app.api.repo.employee import EmployeeRepository
from app.api.repo.employee_pay import EmployeePayRepository
from app.api.repo.employment_period import EmploymentPeriodRepository
from app.api.repo.organization import OrganizationRepository
from app.api.repo.redis import RedisRepository
from app.api.repo.role import RoleRepository
from app.api.repo.uow import UnitOfWorkRepository
from app.api.repo.user import UserRepository
from app.api.schemas.user import CachedUser
from app.api.services.auth import AuthService
from app.api.services.email import EmailService
from app.api.services.employee import EmployeeService
from app.api.services.employee_pay import EmployeePayService
from app.api.services.employment_period import EmploymentPeriodService
from app.api.services.organization import OrganizationService
from app.api.services.otp import OtpService
from app.api.services.role import RoleService
from app.api.services.user import UserService
from app.core.config import get_settings
from app.core.enum import Role
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ErrorCode,
    TokenExpiredError,
)
from app.core.security import Security
from app.database.session import get_session
from app.limiter import _limiter_handler

SETTINGS = get_settings()

# Auth bearer
bearer = HTTPBearer(auto_error=False)

# ------------------- DB dependency ------------------------------ #

DBSession = Annotated[AsyncSession, Depends(get_session)]


# ------------------- Redis dependency ------------------------------ #
async def get_redis_client(request: Request) -> Redis:
    redis_client: Redis = request.app.state.redis
    return redis_client


RedisDep = Annotated[Redis, Depends(get_redis_client)]


# ------------------- Security dependency ------------------------------ #
async def get_security() -> Security:
    return Security()


SecurityDep = Annotated[Security, Depends(get_security)]

#  ------------------- Repo dependency ----------------------------- #


async def get_user_repo(session: DBSession) -> UserRepository:
    return UserRepository(async_session=session)


async def get_redis_repo(redis: RedisDep) -> RedisRepository:
    return RedisRepository(async_redis=redis)


async def get_email_repo(session: DBSession) -> EmailRepository:
    return EmailRepository(async_session=session)


async def get_employee_repo(session: DBSession) -> EmployeeRepository:
    return EmployeeRepository(async_session=session)


async def get_employment_period_repo(
    session: DBSession,
) -> EmploymentPeriodRepository:
    return EmploymentPeriodRepository(async_session=session)


async def get_employee_pay_repo(session: DBSession) -> EmployeePayRepository:
    return EmployeePayRepository(async_session=session)


async def get_organization_repo(session: DBSession) -> OrganizationRepository:
    return OrganizationRepository(async_session=session)


async def get_role_repo(session: DBSession) -> RoleRepository:
    return RoleRepository(async_session=session)


async def get_unit_of_work(session: DBSession) -> UnitOfWorkRepository:
    return UnitOfWorkRepository(async_session=session)


UserRepo = Annotated[UserRepository, Depends(get_user_repo)]
RedisRepo = Annotated[RedisRepository, Depends(get_redis_repo)]
EmailRepo = Annotated[EmailRepository, Depends(get_email_repo)]
EmployeeRepo = Annotated[EmployeeRepository, Depends(get_employee_repo)]
EmploymentPeriodRepo = Annotated[
    EmploymentPeriodRepository, Depends(get_employment_period_repo)
]
EmployeePayRepo = Annotated[EmployeePayRepository, Depends(get_employee_pay_repo)]
OrganizationRepo = Annotated[OrganizationRepository, Depends(get_organization_repo)]
RoleRepo = Annotated[RoleRepository, Depends(get_role_repo)]
UnitOfWorkRepo = Annotated[UnitOfWorkRepository, Depends(get_unit_of_work)]

#  -------------------- Service dependency ---------------------------- #


async def get_user_service(user_repo: UserRepo, redis_repo: RedisRepo) -> UserService:
    return UserService(user_repo=user_repo, redis_repo=redis_repo)


async def get_employee_service(employee_repo: EmployeeRepo) -> EmployeeService:
    return EmployeeService(employee_repo=employee_repo)


async def get_employment_period_service(
    employment_period_repo: EmploymentPeriodRepo,
) -> EmploymentPeriodService:
    return EmploymentPeriodService(employment_period_repo=employment_period_repo)


async def get_employee_pay_service(
    employee_pay_repo: EmployeePayRepo,
) -> EmployeePayService:
    return EmployeePayService(employee_pay_repo=employee_pay_repo)


async def get_email_service(email_repo: EmailRepo) -> EmailService:
    return EmailService(email_repo=email_repo)


async def get_organization_service(
    organization_repo: OrganizationRepo,
) -> OrganizationService:
    return OrganizationService(organization_repo=organization_repo)


async def get_role_service(role_repo: RoleRepo) -> RoleService:
    return RoleService(role_repo=role_repo)


async def get_auth_service(redis_repo: RedisRepo) -> AuthService:
    return AuthService(redis_repo=redis_repo)


async def get_otp_service(redis_repo: RedisRepo) -> OtpService:
    return OtpService(redis_repo=redis_repo)


OtpServiceDep = Annotated[OtpService, Depends(get_otp_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
EmailServiceDep = Annotated[EmailService, Depends(get_email_service)]
EmployeeServiceDep = Annotated[EmployeeService, Depends(get_employee_service)]
EmploymentPeriodServiceDep = Annotated[
    EmploymentPeriodService, Depends(get_employment_period_service)
]
EmployeePayServiceDep = Annotated[EmployeePayService, Depends(get_employee_pay_service)]
OrganizationServiceDep = Annotated[
    OrganizationService, Depends(get_organization_service)
]
RoleServiceDep = Annotated[RoleService, Depends(get_role_service)]

# ------------------------ Auth dependency ---------------------------- #


async def _decode_credentials(
    security: SecurityDep,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
) -> dict:
    if not credentials:
        sentry_logger.warning("Access token not received")
        raise AuthenticationError(
            code=ErrorCode.TOKEN_MISSING, details={"reason": "Access Token Missing"}
        )

    try:
        claims: dict = await security.decode_token(
            credentials.credentials, SETTINGS.ACCESS_TOKEN_SECRET_KEY, "access"
        )
    except TokenExpiredError as exc:
        sentry_logger.warning("Expired access token received")
        raise AuthenticationError(
            code=ErrorCode.TOKEN_EXPIRED, details={"reason": "Access Token Expired"}
        ) from exc

    if not claims:
        sentry_logger.warning("Invalid access token received")
        raise AuthenticationError(
            code=ErrorCode.TOKEN_INVALID, details={"reason": "Invalid Access Token"}
        )

    return claims


AccessTokenClaims = Annotated[dict, Depends(_decode_credentials)]


async def get_current_user(
    user_service: UserServiceDep,
    claims: AccessTokenClaims,
) -> User:
    user: User = await user_service.get_user(
        id=claims.get("sub"), with_role=True, is_verified=True
    )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_active_user(curr_user: CurrentUser):
    if curr_user.is_active is False:
        sentry_logger.warning("User {user_id} is inactive", user_id=curr_user.id)
        raise AuthorizationError(
            code=ErrorCode.USER_INACTIVE, details={"reason": "Inactive user"}
        )
    return curr_user


CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]


async def get_current_cached_user(
    user_service: UserServiceDep,
    claims: AccessTokenClaims,
):
    filters: dict = {"id": claims.get("sub")}
    user: CachedUser | None = await user_service.get_cached_user(**filters)

    if not user:
        filters["is_verified"] = True
        user = await user_service.get_user(
            with_role=True, **filters
        )

        await user_service.cache_user(user)
    return user


CurrentCachedUser = Annotated[CachedUser | User, Depends(get_current_cached_user)]


async def get_current_active_cached_user(cached_user: CurrentCachedUser):
    if cached_user.is_active is False:
        sentry_logger.warning("User {user_id} is inactive", user_id=cached_user.id)
        raise AuthorizationError(
            code=ErrorCode.USER_INACTIVE, details={"reason": "Inactive user"}
        )
    return cached_user


CurrentActiveCachedUser = Annotated[User, Depends(get_current_active_cached_user)]


def require_roles(roles: list[Role]):
    async def role_checker(active_user: CurrentActiveCachedUser):
        if active_user.role.name not in roles:
            raise AuthorizationError(code=ErrorCode.NOT_PERMITTED)
        return active_user

    return role_checker


# ------------------------ Limiter -------------------------------- #
write_limiter = Depends(
    _limiter_handler(
        key=SETTINGS.WRITE_LIMIT_KEY, limit=10, unit="minutes", multiplier=15
    )
)
read_limiter = Depends(
    _limiter_handler(
        key=SETTINGS.READ_LIMIT_KEY, limit=10, unit="minutes", multiplier=1
    )
)
