from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.schemas.response import Error, ErrorResponse
from app.core.exceptions import (
    ActiveEmploymentPeriodError,
    AuthenticationError,
    AuthorizationError,
    CredentialError,
    EntityExistsError,
    ErrorCode,
    GoogleSignInError,
    InvalidEmploymentPeriodError,
    InvalidOtpError,
    NotFoundError,
    OauthSignInError,
    OtpAttemptsExceededError,
    RateLimitExceeded,
    ServerError,
    ServiceUnavailable,
    UserDeactivatedError,
    UserLinkedError,
    create_exception_handler,
)


class ExceptionHandler:
    def __init__(self, app: FastAPI):
        self._app = app

    def add_handlers(self):
        @self._app.exception_handler(RequestValidationError)
        async def validation_exception_handler(req, exc):
            details = {
                ".".join(str(field) for field in err["loc"]): err["msg"]
                for err in exc.errors()
            }

            return JSONResponse(
                content=ErrorResponse(
                    error=Error(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Some fields are missing or invalid. See details.",
                        request_id=req.state.request_id,
                        details=details,
                    )
                ).model_dump(mode="json"),
                status_code=422,
            )

        self._app.add_exception_handler(
            ServerError,
            create_exception_handler(
                status_code=500,
                detail={
                    "status": "error",
                    "message": "Oops! Something went wrong.",
                },
            ),
        )

        self._app.add_exception_handler(
            ServiceUnavailable,
            create_exception_handler(
                status_code=503,
                detail={
                    "status": "error",
                    "message": "Service unavailable! Try again after five minutes",
                },
            ),
        )

        self._app.add_exception_handler(
            AuthenticationError,
            create_exception_handler(
                status_code=401,
                detail={
                    "status": "error",
                    "message": "User not authenticated.",
                },
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=AuthorizationError,
            handler=create_exception_handler(
                status_code=403,
                detail={
                    "status": "error",
                    "message": "User is not authorized to make the requested action",
                },
            ),
        )

        # TODO: Replace error message for google/github sign in error
        self._app.add_exception_handler(
            exc_class_or_status_code=GoogleSignInError,
            handler=create_exception_handler(
                status_code=403,
                detail={
                    "status": "error",
                    "message": "User is not authorized to make the requested action",
                },
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=OauthSignInError,
            handler=create_exception_handler(
                status_code=403,
                detail={
                    "status": "error",
                    "message": "Failed to sign-in with oauth",
                },
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=EntityExistsError,
            handler=create_exception_handler(
                status_code=409,
                detail={
                    "status": "error",
                    "message": (
                        "{entity} already exists with the provided"
                        "{entity_property} {entity_value}"
                    ),
                },
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=UserLinkedError,
            handler=create_exception_handler(
                status_code=409,
                detail={
                    "status": "error",
                    "message": "User linked to an existing employee"
                },
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=UserDeactivatedError,
            handler=create_exception_handler(
                status_code=409,
                detail={
                    "status": "error",
                    "message": (
                        "This account is deactivated. Reactivate your account "
                        "to continue."
                    ),
                },
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=InvalidOtpError,
            handler=create_exception_handler(
                detail={
                    "status": "error",
                    "message": "Invalid otp received",
                },
                status_code=400,
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=InvalidEmploymentPeriodError,
            handler=create_exception_handler(
                detail={
                    "status": "error",
                    "message": "{reason}",
                },
                status_code=400,
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=ActiveEmploymentPeriodError,
            handler=create_exception_handler(
                detail={
                    "status": "error",
                    "message": (
                        "An active employment period already exists. Update its "
                        "end_date before creating a new one."
                    ),
                },
                status_code=409,
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=NotFoundError,
            handler=create_exception_handler(
                status_code=404,
                detail={
                    "status": "error",
                    "message": "{entity} not found",
                },
            ),
        )

        self._app.add_exception_handler(
            exc_class_or_status_code=OtpAttemptsExceededError,
            handler=create_exception_handler(
                status_code=400,
                detail={
                    "message": "Too many wrong attempts. Request a new code to continue."
                },
            ),
        )

        self._app.add_exception_handler(
            CredentialError,
            create_exception_handler(
                detail={
                    "status": "error",
                    "message": "Invalid credentials!",
                },
                status_code=400,
            ),
        )

        self._app.add_exception_handler(
            RateLimitExceeded,
            create_exception_handler(
                429,
                {"message": "Too many requests. Try again in {retry_after} seconds."},
            ),
        )
