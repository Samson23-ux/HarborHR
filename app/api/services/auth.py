from datetime import UTC, datetime
from uuid import UUID, uuid4, uuid7

import sentry_sdk
import sentry_sdk.logger as sentry_logger

from app.api.models.user import User
from app.api.repo.email import EmailRepository
from app.api.repo.organization import OrganizationRepository
from app.api.repo.redis import RedisRepository
from app.api.repo.role import RoleRepository
from app.api.repo.uow import UnitOfWorkRepository
from app.api.repo.user import UserRepository
from app.api.schemas.auth import (
    EmailLogin,
    EmailSignUp,
    EmailVerify,
    GoogleSignUp,
    ReactivateAccount,
    ResendOtp,
    TokenData,
)
from app.api.schemas.email import EmailInDB
from app.api.schemas.organization import OrganizationInDB
from app.api.schemas.user import (
    EmailUserResponse,
    GoogleUserResponse,
    UserInDB,
    UserResponse,
)
from app.api.services.email import EmailService
from app.api.services.organization import OrganizationService
from app.api.services.otp import OtpService
from app.api.services.role import RoleService
from app.api.services.user import UserService
from app.core.config import get_settings
from app.core.enum import OtpPurpose, Role
from app.core.exceptions import (
    AuthenticationError,
    CredentialError,
    ErrorCode,
    InvalidOtpError,
    ServerError,
    TokenExpiredError,
    UserExistsError,
)
from app.core.security import Security
from app.email_texts import verification_message
from app.worker.tasks.email import send_email

SETTINGS = get_settings()


def _session_key(user_id: UUID) -> str:
    return f"sessions:{user_id!s}"


def _refresh_expire() -> int:
    return SETTINGS.REFRESH_TOKEN_EXPIRE_TIME * 24 * 3600


class AuthService:
    def __init__(self, redis_repo: RedisRepository):
        self._uow: UnitOfWorkRepository | None = None
        self._user_service: UserService | None = None
        self._redis_repo = redis_repo

    # SETTINGS = get_settings()

    async def _setup_uow(self, uow: UnitOfWorkRepository):
        self._uow = uow

    async def _uow_user_otp_email(self, uow: UnitOfWorkRepository):
        await self._setup_uow(uow)

        user_repo = self._uow.repo(UserRepository)
        email_repo = self._uow.repo(EmailRepository)
        organization_repo = self._uow.repo(OrganizationRepository)
        role_repo = self._uow.repo(RoleRepository)

        self._user_service = UserService(
            user_repo=user_repo, redis_repo=self._redis_repo
        )
        self._email_service = EmailService(email_repo=email_repo)
        self._organization_service = OrganizationService(
            organization_repo=organization_repo
        )
        self._role_service = RoleService(role_repo=role_repo)

    async def _uow_google_sign_in(self, uow: UnitOfWorkRepository):
        await self._setup_uow(uow)

        user_repo = self._uow.repo(UserRepository)
        role_repo = self._uow.repo(RoleRepository)
        organization_repo = self._uow.repo(OrganizationRepository)

        self._user_service = UserService(
            user_repo=user_repo, redis_repo=self._redis_repo
        )
        self._organization_service = OrganizationService(
            organization_repo=organization_repo
        )
        self._role_service = RoleService(role_repo=role_repo)

    async def _get_tokens(
        self, user_id: UUID, organization_id: UUID | None, security: Security
    ):
        token_data: TokenData = TokenData(
            user_id=user_id, organization_id=organization_id, session_id=uuid4()
        )
        access_token, refresh_token_payload = await security.prepare_tokens(token_data)

        try:
            await self._redis_repo.create_hset(
                _session_key(user_id),
                {
                    str(token_data.session_id): refresh_token_payload.get(
                        "refresh_token_id"
                    )
                },
                _refresh_expire(),
            )

            sentry_logger.info(
                "Access and refresh tokens created for user {user_id}",
                user_id=user_id,
            )

            return access_token, refresh_token_payload.get("refresh_token")
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error("Error occurred while saving refresh token to redis")
            raise ServerError() from exc

    async def _revoke_session(self, refresh_token: str, security: Security):
        try:
            claims = await security.decode_token(
                refresh_token, SETTINGS.REFRESH_TOKEN_SECRET_KEY, "refresh"
            )

            if not claims:
                sentry_logger.warning(
                    "Invalid refresh token received while revoking session"
                )
                raise AuthenticationError(
                    code=ErrorCode.REFRESH_TOKEN_INVALID,
                    details={"reason": "Invalid Refresh Token"},
                )

            await self._redis_repo.delete_session(
                _session_key(claims.get("sub")), claims.get("sid")
            )
        except TokenExpiredError as exc:
            sentry_logger.warning("Refresh token expired while revoking session")
            raise AuthenticationError(
                code=ErrorCode.REFRESH_TOKEN_EXPIRED,
                details={"reason": "Refresh Token Expired"},
            ) from exc
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while revoking user {user_id} session",
                user_id=claims.get("sub"),
            )
            raise ServerError() from exc

    async def _revoke_all_sessions(self, refresh_token: str, security: Security):
        try:
            claims = await security.decode_token(
                refresh_token, SETTINGS.REFRESH_TOKEN_SECRET_KEY, "refresh"
            )

            if not claims:
                sentry_logger.warning(
                    "Invalid refresh token received while revoking all sessions"
                )
                raise AuthenticationError(
                    code=ErrorCode.REFRESH_TOKEN_INVALID,
                    details={"reason": "Invalid Refresh Token"},
                )

            await self._redis_repo.delete_key(_session_key(claims.get("sub")))
        except TokenExpiredError as exc:
            sentry_logger.warning("Refresh token expired while revoking all sessions")
            raise AuthenticationError(
                code=ErrorCode.REFRESH_TOKEN_EXPIRED,
                details={"reason": "Refresh Token Expired"},
            ) from exc
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while revoking all user {user_id} sessions",
                user_id=claims.get("sub"),
            )
            raise ServerError() from exc

    async def _send_email(
        self,
        otp_service: OtpService,
        email_subject: str,
        recipient_email: str,
        user_id: UUID,
        otp_purpose: str,
    ):
        email_db: EmailInDB = EmailInDB(id=uuid7(), processed_email=recipient_email)
        await self._email_service.create_email(email_db)

        send_email.apply_async(
            priority=3,
            kwargs={
                "email_subject": email_subject,
                "email_message": verification_message(
                    await otp_service.create_otp(user_id, otp_purpose)
                ),
                "recipient_email": recipient_email,
            },
        )

    async def sign_up_with_email(
        self,
        signup: EmailSignUp,
        otp_service: OtpService,
        security: Security,
        uow: UnitOfWorkRepository,
    ):
        await self._uow_user_otp_email(uow)

        try:
            existing_user: User | None = await self._user_service.get_existing_user(
                signup.email
            )

            if existing_user and existing_user.email and existing_user.is_verified:
                sentry_logger.warning(
                    "User {user_id} exists with the email provided for sign-up",
                    user_id=existing_user.id,
                )
                raise UserExistsError(user_email=signup.email)
        except UserExistsError:
            raise
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while retrieving existing user for email sign-up"
            )
            raise ServerError() from exc

        try:
            hashed_password: str = await security.hash_password(signup.password)

            """Link an existing verified google signup account"""

            if existing_user:
                existing_user.email = signup.email
                existing_user.hashed_password = hashed_password

                existing_user.updated_at = datetime.now(UTC)
                await self._user_service.update_user(existing_user)

            if not existing_user:
                org = await self._organization_service.create_organization(
                    OrganizationInDB(
                        id=uuid7(),
                        name=signup.organization_name,
                        country=signup.organization_country,
                    )
                )

                role_id: UUID | None = await self._role_service.select_role_id(
                    name=Role.ADMIN
                )

                user = UserInDB(
                    id=uuid7(),
                    email=signup.email,
                    role_id=role_id,
                    is_active=True,
                    organization_id=org.id,
                    hashed_password=hashed_password,
                )

                await self._user_service.create_user(user, signup.email)

            user_id = existing_user.id if existing_user else user.id

            await self._uow.commit()
            await self._send_email(
                otp_service,
                OtpPurpose.EMAIL_VERIFICATION,
                signup.email,
                user_id,
                OtpPurpose.EMAIL_VERIFICATION,
            )

            sentry_logger.info(
                "Email and password sign-up completed for user {user_id}",
                user_id=user_id,
            )
        except Exception as exc:
            await self._uow.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while creating user",
            )
            raise ServerError() from exc

    async def sign_up_with_google(
        self,
        payload: dict,
        signup: GoogleSignUp,
        security: Security,
        uow: UnitOfWorkRepository,
    ) -> tuple[str, str]:
        await self._uow_user_otp_email(uow)

        try:
            user_info: dict = payload.get("userinfo")

            google_id: str = user_info.get("sub")
            user_email: str = user_info.get("email")

            existing_user: User | None = await self._user_service.get_existing_user(
                user_email
            )

            """Link an existing email signup account"""

            if existing_user and existing_user.email:
                if not existing_user.is_verified:
                    existing_user.email = None
                    existing_user.hashed_password = None
                    existing_user.is_verified = True

                existing_user.google_id = google_id
                existing_user.google_email = user_email

                existing_user.updated_at = datetime.now(UTC)
                await self._user_service.update_user(existing_user)

            if not existing_user:
                org = await self._organization_service.create_organization(
                    OrganizationInDB(
                        id=uuid7(),
                        name=signup.organization_name,
                        country=signup.organization_country,
                    )
                )

                role_id: UUID | None = await self._role_service.select_role_id(
                    name=Role.ADMIN
                )

                user = UserInDB(
                    id=uuid7(),
                    is_active=True,
                    is_verified=True,
                    role_id=role_id,
                    organization_id=org.id,
                    google_id=google_id,
                    google_email=user_email,
                )
                await self._user_service.create_user(user, user_email)

            user_id = existing_user.id if existing_user else user.id

            if existing_user and existing_user.organization:
                organization_id = existing_user.organization.id
            else:
                organization_id = user.organization_id

            await self._uow.commit()

            access_token, refresh_token = await self._get_tokens(
                user_id, organization_id, security
            )

            sentry_logger.info(
                "Google sign-in completed for user {user_id}",
                user_id=user_id,
            )

            return access_token, refresh_token
        except Exception as exc:
            await self._uow.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error("Error occurred while signing in with google account")
            raise ServerError() from exc

    async def verify_account(
        self,
        otp_service: OtpService,
        user_service: UserService,
        email_verify: EmailVerify,
    ):
        existing_user: User | None = await user_service._get_user(
            email=email_verify.email
        )

        if not existing_user:
            sentry_logger.warning(
                "User not found with email in an attempt to verify account"
            )
            raise InvalidOtpError()

        await otp_service.verify_otp(
            existing_user.id, email_verify.otp_purpose, email_verify.otp_code
        )

        try:
            if email_verify.otp_purpose == OtpPurpose.EMAIL_VERIFICATION:
                existing_user.is_verified = True
                err_msg = "Error occurred while trying to verify user {user_id} account"

            if email_verify.otp_purpose == OtpPurpose.ACCOUNT_REACTIVATION:
                existing_user.is_active = True
                err_msg = (
                    "Error occurred while trying to reactivate user {user_id} account"
                )

            existing_user.updated_at = datetime.now(UTC)
            await user_service.update_user(existing_user, commit=True)

            sentry_logger.info(
                "User {user_id} {otp_purpose} completed",
                user_id=existing_user.id,
                otp_purpose=email_verify.otp_purpose,
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                err_msg,
                user_id=existing_user.id,
            )
            raise ServerError() from exc

    async def resend_otp(
        self,
        otp_resend: ResendOtp,
        otp_service: OtpService,
        uow: UnitOfWorkRepository,
    ):
        await self._uow_user_otp_email(uow)

        filters = {"email": otp_resend.email}

        if otp_resend.otp_purpose == OtpPurpose.EMAIL_VERIFICATION:
            filters["is_verified"] = False

        if otp_resend.otp_purpose == OtpPurpose.ACCOUNT_REACTIVATION:
            filters["is_active"] = False

        existing_user: User | None = await self._user_service._get_user(**filters)

        if not existing_user:
            sentry_logger.warning("User not found for resend otp")
            return

        try:
            await self._uow.commit()
            await self._send_email(
                otp_service,
                otp_resend.otp_purpose,
                otp_resend.email,
                existing_user.id,
                otp_resend.otp_purpose,
            )

            sentry_logger.info(
                "OTP code resent to user {user_id}",
                user_id=existing_user.id,
            )
        except Exception as exc:
            await self._uow.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while resending otp to user {user_id}",
                user_id=existing_user.id,
            )
            raise ServerError() from exc

    async def login(
        self, email_login: EmailLogin, user_service: UserService, security: Security
    ):
        user_email: str = email_login.email
        existing_user: User | None = await user_service._get_user(
            email=user_email, is_verified=True, is_active=True
        )

        if not existing_user:
            sentry_logger.warning(
                "Invalid credentials received from user in an attempt to login. User not found",
            )
            raise CredentialError()

        if not await security.verify_password(
            email_login.password, existing_user.hashed_password
        ):
            sentry_logger.warning(
                "Invalid credentials received from user in an attempt to login. Wrong password",
            )
            raise CredentialError()

        organization_id = (
            existing_user.organization.id if existing_user.organization else None
        )

        access_token, refresh_token = await self._get_tokens(
            existing_user.id, organization_id, security
        )

        sentry_logger.info(
            "Login completed for user {user_id}",
            user_id=existing_user.id,
        )

        return access_token, refresh_token

    async def create_auth_tokens(
        self, refresh_token: str, user_service: UserService, security: Security
    ):
        try:
            claims = await security.decode_token(
                refresh_token, SETTINGS.REFRESH_TOKEN_SECRET_KEY, "refresh"
            )

            if not claims:
                sentry_logger.warning(
                    "Invalid refresh token received in an attempt to refresh tokens"
                )
                raise AuthenticationError(
                    code=ErrorCode.REFRESH_TOKEN_INVALID,
                    details={"reason": "Invalid Refresh Token"},
                )
        except TokenExpiredError as exc:
            sentry_logger.warning("Refresh token expired for token refresh")
            raise AuthenticationError(
                code=ErrorCode.REFRESH_TOKEN_EXPIRED,
                details={"reason": "Refresh Token Expired"},
            ) from exc

        user_id = claims.get("sub")

        existing_user: User | None = await user_service._get_user(
            id=user_id, is_verified=True, is_active=True
        )

        if not existing_user:
            sentry_logger.warning(
                "User {user_id} not found during refresh", user_id=user_id
            )
            raise AuthenticationError(
                code=ErrorCode.REFRESH_TOKEN_INVALID,
                details={"reason": "User not found"},
            )

        organization_id = (
            existing_user.organization.id if existing_user.organization else None
        )

        token_data: TokenData = TokenData(
            user_id=user_id,
            organization_id=organization_id,
            session_id=claims.get("sid"),
        )
        access_token, refresh_token_payload = await security.prepare_tokens(token_data)

        try:
            refresh_state = await self._redis_repo.rotate_refresh_token(
                _session_key(user_id),
                claims.get("sid"),
                claims.get("jti"),
                refresh_token_payload.get("refresh_token_id"),
                _refresh_expire(),
            )
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error("Error occurred while rotating refresh token")
            raise ServerError() from exc

        if refresh_state == 0:
            sentry_logger.warning(
                "Refresh token for an ended session received for user {user_id}",
                user_id=user_id,
            )
            raise AuthenticationError(
                code=ErrorCode.REFRESH_TOKEN_INVALID,
                details={"reason": "Invalid Refresh Token"},
            )

        if refresh_state == -1:
            sentry_logger.error(
                "Reused refresh token received for user {user_id}", user_id=user_id
            )
            raise AuthenticationError(
                code=ErrorCode.REFRESH_TOKEN_REUSED,
                details={"reason": "Refresh Token Used"},
            )

        sentry_logger.info(
            "Access and refresh tokens created for user {user_id}",
            user_id=user_id,
        )

        return access_token, refresh_token_payload.get("refresh_token")

    async def get_current_user(
        self, curr_user: User
    ) -> EmailUserResponse | GoogleUserResponse | UserResponse:
        sentry_logger.info("User {user_id} account retrieved", user_id=curr_user.id)
        if curr_user.email:
            return EmailUserResponse.model_validate(curr_user)
        elif curr_user.google_email:
            return GoogleUserResponse.model_validate(curr_user)
        else:
            return UserResponse.model_validate(curr_user)

    async def logout(
        self,
        curr_user: User,
        refresh_token: str,
        security: Security,
    ):
        await self._revoke_session(refresh_token, security)

        sentry_logger.info(
            "User {user_id} account logout completed", user_id=curr_user.id
        )

    async def deactivate_account(
        self,
        curr_user: User,
        user_service: UserService,
        refresh_token: str,
        security: Security,
    ):
        curr_user.is_active = False
        curr_user.updated_at = datetime.now(UTC)

        await user_service.update_user(curr_user, commit=True)
        await self._revoke_all_sessions(refresh_token, security)

        sentry_logger.info("User {user_id} account deactivated", user_id=curr_user.id)

    async def reactivate_account(
        self,
        otp_service: OtpService,
        user_service: UserService,
        email_service: EmailService,
        reactivate: ReactivateAccount,
    ):
        self._email_service = email_service

        user: User | None = await user_service.get_user_for_reactivation(
            reactivate.email
        )

        if user:
            await self._send_email(
                otp_service,
                OtpPurpose.ACCOUNT_REACTIVATION,
                user.email,
                user.id,
                OtpPurpose.ACCOUNT_REACTIVATION,
            )

            sentry_logger.info(
                "Reactivation email sent for user {user_id}", user_id=user.id
            )
