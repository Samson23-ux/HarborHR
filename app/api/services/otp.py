import secrets
from uuid import UUID

import sentry_sdk
import sentry_sdk.logger as sentry_logger

from app.api.repo.redis import RedisRepository
from app.core.config import get_settings
from app.core.exceptions import InvalidOtpError, OtpAttemptsExceededError, ServerError
from app.core.security import Security

SETTINGS = get_settings()


class OtpService:
    def __init__(self, security: Security, redis_repo: RedisRepository):
        self._security = security
        self._redis_repo = redis_repo

    @staticmethod
    def _otp_key(user_id: UUID, otp_purpose: str) -> str:
        return f"otp:{user_id!s}:{otp_purpose}"

    def _hash_otp(self, otp: str) -> str:
        return self._security.hash_value_256(otp, SETTINGS.OTP_SECRET_KEY)

    @staticmethod
    def _otp_expire() -> int:
        return SETTINGS.OTP_EXPIRE_TIME * 60

    async def create_otp(self, user_id: UUID, otp_purpose: str) -> str:
        otp: str = str(secrets.randbelow(900000) + 100000)

        try:
            await self._redis_repo.create_hset(
                self._otp_key(user_id, otp_purpose),
                {"code": self._hash_otp(otp), "attempts": 0},
                self._otp_expire(),
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while creating otp for user {user_id}",
                user_id=str(user_id),
            )

            raise ServerError() from exc

        return otp

    async def verify_otp(self, user_id: UUID, otp_purpose: str, otp: str):
        try:
            otp_state = await self._redis_repo.consume_otp_code(
                self._otp_key(user_id, otp_purpose),
                self._hash_otp(otp),
                SETTINGS.OTP_MAX_ATTEMPTS,
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while verifying otp for user {user_id}",
                user_id=str(user_id),
            )
            raise ServerError() from exc

        if otp_state == 1:
            return

        sentry_logger.warning(
            "Invalid otp received for user {user_id}",
            user_id=str(user_id),
        )

        if otp_state == -1:
            raise OtpAttemptsExceededError()
        raise InvalidOtpError()
