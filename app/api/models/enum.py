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
