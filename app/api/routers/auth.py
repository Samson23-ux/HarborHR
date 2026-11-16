import sentry_sdk
import sentry_sdk.logger as sentry_logger
from authlib.integrations.base_client.errors import MismatchingStateError, OAuthError
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse
from pydantic_core import ValidationError

from app.api.schemas.auth import (
    EmailLogin,
    EmailSignUp,
    EmailVerify,
    GoogleSignUp,
    LogoutResponse,
    OtpResendResponse,
    ReactivateAccount,
    ResendOtp,
    SignUpResponse,
    Token,
)
from app.api.schemas.response import SuccessResponse
from app.api.schemas.user import (
    EmailUserResponse,
    GoogleUserResponse,
    UserResponse,
)
from app.core.config import get_settings
from app.core.enum import OauthFailure
from app.core.exceptions import (
    ErrorCode,
    GoogleSignInError,
    OauthSignInError,
)
from app.deps import (
    AuthServiceDep,
    CurrentActiveUser,
    EmailServiceDep,
    OtpServiceDep,
    SecurityDep,
    UnitOfWorkRepo,
    UserServiceDep,
    read_limiter,
    write_limiter,
)

router = APIRouter()

SETTINGS = get_settings()


def _refresh_expire() -> int:
    return SETTINGS.REFRESH_TOKEN_EXPIRE_TIME * 24 * 3600


def _secure_cookie() -> bool:
    return SETTINGS.ENVIRONMENT == "production"


@router.post(
    "/auth/signup",
    status_code=201,
    response_model=SuccessResponse[SignUpResponse],
    description=(
        "Sign up with email and password."
        "A verification code is sent to the user's email on completion"
    ),
    dependencies=[write_limiter],
)
async def sign_up_with_email(
    request: Request,
    security: SecurityDep,
    signup: EmailSignUp,
    otp_service: OtpServiceDep,
    auth_service: AuthServiceDep,
    uow: UnitOfWorkRepo,
):
    await auth_service.sign_up_with_email(signup, otp_service, security, uow)
    return SuccessResponse(
        message=(
            "Sign up completed successfully."
            "Check your email for verification code and instructions"
        )
    )


@router.post(
    "/auth/google",
    status_code=302,
    response_class=RedirectResponse,
    description="Sign in with Google account",
    dependencies=[write_limiter],
)
async def sign_in_with_google(
    request: Request, signup: GoogleSignUp, security: SecurityDep
):
    request.session["google_signup"] = {
        "organization_name": signup.organization_name,
        "organization_country": signup.organization_country,
    }

    redirect_uri = SETTINGS.GOOGLE_CALLBACK_URL or request.url_for("google_callback")
    return await security.oauth.google.authorize_redirect(request, redirect_uri)


@router.get(
    "/auth/google/callback",
    status_code=200,
    response_model=SuccessResponse[Token],
    description="Google redirect uri",
)
async def google_callback(
    request: Request,
    response: Response,
    security: SecurityDep,
    uow: UnitOfWorkRepo,
    auth_service: AuthServiceDep,
):
    error: str | None = request.query_params.get("error")

    if error:
        failure = (
            OauthFailure.ACCESS_DENIED
            if error == "access_denied"
            else OauthFailure.OAUTH_FAILED
        )
        code = (
            ErrorCode.OAUTH_ACCESS_DENIED
            if failure == "access_denied"
            else ErrorCode.OAUTH_FAILED
        )

        raise GoogleSignInError(code=code, details={"reason": failure})

    try:
        signup = GoogleSignUp(**request.session["google_signup"])
    except ValidationError:
        raise GoogleSignInError(
            code=ErrorCode.OAUTH_ACCESS_DENIED,
            details={"reason": "Invalid payload received"},
        )

    try:
        payload = await security.oauth.google.authorize_access_token(request)
    except MismatchingStateError as exc:
        sentry_sdk.capture_exception(exc)
        sentry_logger.error("State mismatch for google sign-in")
        raise OauthSignInError(
            code=ErrorCode.OAUTH_STATE_MISMATCH,
            details={"reason": "State mismatch for google sign-in"},
        ) from exc
    except OAuthError as exc:
        sentry_sdk.capture_exception(exc)
        sentry_logger.error("Google oauth failed")
        raise OauthSignInError(
            code=ErrorCode.OAUTH_FAILED,
            details={"reason": "Oauth failed for google sign-in"},
        )

    access_token, refresh_token = await auth_service.sign_up_with_google(
        payload, signup, security, uow
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=_refresh_expire(),
        secure=_secure_cookie(),
        samesite="lax",
    )

    return SuccessResponse(data=Token(access_token=access_token))


@router.patch(
    "/auth/verify",
    status_code=200,
    response_model=SuccessResponse[EmailUserResponse],
    description="Verify account by submitting the received otp code",
    dependencies=[write_limiter],
)
async def verify_account(
    request: Request,
    email_verify: EmailVerify,
    user_service: UserServiceDep,
    otp_service: OtpServiceDep,
    auth_service: AuthServiceDep,
):
    await auth_service.verify_account(otp_service, user_service, email_verify)
    return SuccessResponse(message="User email verified successfully")


@router.post(
    "/auth/verify/resend",
    status_code=201,
    description="Resend verification code",
    response_model=SuccessResponse[OtpResendResponse],
    dependencies=[write_limiter],
)
async def resend_otp(
    request: Request,
    otp_resend: ResendOtp,
    otp_service: OtpServiceDep,
    auth_service: AuthServiceDep,
    uow: UnitOfWorkRepo,
):
    await auth_service.resend_otp(otp_resend, otp_service, uow)
    return SuccessResponse(
        message="OTP sent successfully. Check your email for instructions"
    )


@router.post(
    "/auth/login",
    status_code=201,
    description="Login with email and password",
    response_model=SuccessResponse[Token],
    dependencies=[write_limiter],
)
async def login(
    request: Request,
    response: Response,
    security: SecurityDep,
    email_login: EmailLogin,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    access_token, refresh_token = await auth_service.login(
        email_login, user_service, security
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=_refresh_expire(),
        secure=_secure_cookie(),
        samesite="lax",
    )
    return SuccessResponse(
        message="Login completed successfully", data=Token(access_token=access_token)
    )


@router.post(
    "/auth/refresh",
    status_code=201,
    response_model=SuccessResponse[Token],
    description="Create new access token for user with a valid refresh token",
    dependencies=[write_limiter],
)
async def create_new_token(
    request: Request,
    response: Response,
    security: SecurityDep,
    user_service: UserServiceDep,
    auth_service: AuthServiceDep,
):
    refresh_token: str | None = request.cookies.get("refresh_token")
    access_token, refresh_token = await auth_service.create_auth_tokens(
        refresh_token, user_service, security
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=_refresh_expire(),
        secure=_secure_cookie(),
        samesite="lax",
    )
    return SuccessResponse(
        message="Token created successfully", data=Token(access_token=access_token)
    )


@router.get(
    "/auth/me",
    status_code=200,
    description="Get current active user",
    response_model=SuccessResponse[
        EmailUserResponse | GoogleUserResponse | UserResponse
    ],
    dependencies=[read_limiter],
)
async def get_current_user(
    request: Request,
    curr_user: CurrentActiveUser,
    auth_service: AuthServiceDep,
):
    user: (
        EmailUserResponse | GoogleUserResponse | UserResponse
    ) = await auth_service.get_current_user(curr_user)
    return SuccessResponse(message="User retrieved successfully", data=user)


@router.post(
    "/auth/logout",
    status_code=201,
    response_model=SuccessResponse[LogoutResponse],
    description="Log out account",
    dependencies=[write_limiter],
)
async def log_out(
    request: Request,
    security: SecurityDep,
    curr_user: CurrentActiveUser,
    auth_service: AuthServiceDep,
):
    refresh_token: str | None = request.cookies.get("refresh_token")
    await auth_service.logout(curr_user, refresh_token, security)
    return SuccessResponse(message="Log out completed successfully")


@router.patch(
    "/auth/reactivate",
    status_code=200,
    description="Reactivate account",
    dependencies=[write_limiter],
)
async def reactivate_account(
    request: Request,
    otp_service: OtpServiceDep,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
    email_service: EmailServiceDep,
    reactivate: ReactivateAccount,
):
    await auth_service.reactivate_account(
        otp_service, user_service, email_service, reactivate
    )


@router.delete(
    "/auth/deactivate",
    status_code=204,
    description="Deactivate account",
    dependencies=[write_limiter],
)
async def deactivate_account(
    request: Request,
    security: SecurityDep,
    curr_user: CurrentActiveUser,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    refresh_token: str | None = request.cookies.get("refresh_token")
    await auth_service.deactivate_account(
        curr_user, user_service, refresh_token, security
    )
