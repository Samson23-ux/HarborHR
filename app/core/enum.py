from enum import StrEnum


class UserType(StrEnum):
    EMAIL = "email"
    GOOGLE = "google"


class EmailStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


class OauthFailure(StrEnum):
    OAUTH_FAILED = "oauth_failed"
    ACCESS_DENIED = "access_denied"


class Role(StrEnum):
    STAFF = "staff"
    ADMIN = "admin"
    EMPLOYEE = "employee"
    PAYROLL_OFFICER = "payroll_officer"


class InviteStatus(StrEnum):
    USED = "used"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ErrorCode(StrEnum):
    """Machine-readable error codes returned to clients. Single source of truth."""

    # server
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    MAXIMUM_RETRY_ERROR = "MAXIMUM_RETRY_ERROR"

    # access token
    TOKEN_MISSING = "TOKEN_MISSING"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"

    # refresh token
    REFRESH_TOKEN_INVALID = "REFRESH_TOKEN_INVALID"
    REFRESH_TOKEN_EXPIRED = "REFRESH_TOKEN_EXPIRED"
    REFRESH_TOKEN_REUSED = "REFRESH_TOKEN_REUSED"

    # authorization
    NOT_PERMITTED = "NOT_PERMITTED"
    USER_INACTIVE = "USER_INACTIVE"

    # oauth
    GOOGLE_SIGN_IN_FAILED = "GOOGLE_SIGN_IN_FAILED"
    OAUTH_FAILED = "OAUTH_FAILED"
    OAUTH_ACCESS_DENIED = "OAUTH_ACCESS_DENIED"
    OAUTH_STATE_MISMATCH = "OAUTH_STATE_MISMATCH"

    # user / account
    UNVERIFIED_EMAIL = "UNVERIFIED_EMAIL"
    USER_EXISTS = "USER_EXISTS"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"

    # otp
    INVALID_OTP = "INVALID_OTP"
    OTP_ATTEMPTS_EXCEEDED = "OTP_ATTEMPTS_EXCEEDED"

    # validation
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # rate limit
    RATE_LIMITED = "RATE_LIMITED"
