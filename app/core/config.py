from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="allow", case_sensitive=False
    )

    # environment
    ENVIRONMENT: str = "development"

    # api details
    API_PREFIX: str = "/api/v1"
    API_TITLE: str = "HarborHR"
    API_VERSION: str = "v1.0"
    API_DESCRIPTION: str = "A payroll engine built for Nigerian SMEs"

    # async db
    ASYNC_APP_DB_URL: str
    ASYNC_OWNER_DB_URL: str

    # sync db
    SYNC_APP_DB_URL: str

    # test db
    ASYNC_APP_TEST_DB_URL: str
    ASYNC_OWNER_TEST_DB_URL: str

    # Argon2
    ARGON2_PASSWORD_PEPPER: str

    # JWT
    JWT_TOKEN_ISS: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_TIME: int = 10
    REFRESH_TOKEN_EXPIRE_TIME: int = 7
    ACCESS_TOKEN_SECRET_KEY: str
    REFRESH_TOKEN_SECRET_KEY: str

    # redis
    REDIS_URL: str
    TEST_REDIS_URL: str

    # sentry
    SENTRY_SDK_DSN: str

    # google oauth
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_CALLBACK_URL: str | None = None
    GOOGLE_OAUTH_URL: str = (
        "https://accounts.google.com/.well-known/openid-configuration"
    )

    # session middleware
    SESSION_SECRET_KEY: str

    # rabbitmq
    BROKER_URL: str

    # resend email
    API_EMAIL: str
    RESEND_API_KEY: str

    # notification
    IDEMPOTENCY_KEY_TTL: int = 60 * 60 * 24

    # otp
    OTP_SECRET_KEY: str
    OTP_EXPIRE_TIME: int = 15
    OTP_MAX_ATTEMPTS: int = 5

    # rate limit keys
    READ_LIMIT_KEY: str = "limiter:read"
    WRITE_LIMIT_KEY: str = "limiter:write"


@lru_cache(maxsize=1)
def get_settings():
    return Settings()
