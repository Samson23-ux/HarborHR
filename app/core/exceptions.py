from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse

from app.api.schemas.response import Error, ErrorResponse
from app.core.enum import ErrorCode


class AppException(Exception):
    """Base Exception class"""

    def __init__(self, code: str):
        self.code = code


class ServerError(AppException):
    """Internal Server error."""

    def __init__(self):
        super().__init__(ErrorCode.INTERNAL_ERROR)


class ServiceUnavailable(AppException):
    """Service unavailable temporarily"""

    def __init__(self):
        super().__init__(ErrorCode.UPSTREAM_ERROR)


class MaxRetriesError(AppException):
    """Maximum retries exceeded"""

    def __init__(self, error: str):
        super().__init__(ErrorCode.MAXIMUM_RETRY_ERROR)
        self.error = error


class AuthenticationError(AppException):
    """User not authenticated."""

    def __init__(self, code=None, details=None):
        if details is None:
            details = {}
        super().__init__(code or ErrorCode.TOKEN_INVALID)
        self.details = details


class GoogleSignInError(AppException):
    """Google sign in failed"""

    def __init__(self, code=None, details=None):
        if details is None:
            details = {}
        super().__init__(code or ErrorCode.GOOGLE_SIGN_IN_FAILED)
        self.details = details


class OauthSignInError(AppException):
    """Handle likely CSRF attack on tate mismatch"""

    def __init__(self, code=None, details=None):
        if details is None:
            details = {}
        super().__init__(code or ErrorCode.OAUTH_FAILED)
        self.details = details


class TokenExpiredError(AppException):
    """JWT token expired"""

    def __init__(self):
        super().__init__(ErrorCode.TOKEN_EXPIRED)


class AuthorizationError(AppException):
    """User not authorized"""

    def __init__(self, code=None, details=None):
        if details is None:
            details = {}
        super().__init__(code or ErrorCode.NOT_PERMITTED)
        self.details = details


class UserExistsError(AppException):
    """User already exists"""

    def __init__(self, user_email: str):
        super().__init__(ErrorCode.USER_EXISTS)
        self.user_email = user_email


class NotFoundError(AppException):
    """Entity not found"""

    def __init__(self, entity: str):
        super().__init__(ErrorCode.NOT_FOUND)
        self.entity = entity


class InvalidOtpError(AppException):
    """Invalid otp received"""

    def __init__(self):
        super().__init__(ErrorCode.INVALID_OTP)


class OtpAttemptsExceededError(AppException):
    """Too many wrong otp attempts; a new code must be requested."""

    def __init__(self):
        super().__init__(ErrorCode.OTP_ATTEMPTS_EXCEEDED)


class CredentialError(AppException):
    """wrong credentials provided"""

    def __init__(self):
        super().__init__(ErrorCode.INVALID_CREDENTIALS)


class RateLimitExceeded(AppException):
    def __init__(self, retry_after: int):
        super().__init__(ErrorCode.RATE_LIMITED)
        self.retry_after = retry_after
        self.headers = {"Retry-After": str(retry_after)}


def create_exception_handler(
    status_code: int, detail: dict
) -> Callable[[Request, AppException], Awaitable[JSONResponse]]:
    async def exception_handler(request: Request, exc: AppException):
        message: str = detail.get("message").format(**exc.__dict__)
        error = Error(
            code=exc.code or detail.get("code"),
            message=message,
            request_id=request.state.request_id,
            details=getattr(exc, "details", None),
        )
        content = ErrorResponse(error=error)

        return JSONResponse(
            content=content.model_dump(mode="json"),
            status_code=status_code,
            headers=getattr(exc, "headers", None),
        )

    return exception_handler
