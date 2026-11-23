import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4, uuid7

import httpx
import pytest
from joserfc import jwt
from joserfc.jwk import OctKey
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.core.enum import ErrorCode
from app.core.security import Security
from app.deps import get_security
from app.main import app
from test.conftest import (
    _get_signup_payload,
    _get_test_user,
    add_user_to_db,
    get_user_from_db,
)

SETTINGS = get_settings()

TEST_GOOGLE_PROFILE = {
    "sub": "randomfakeid",
    "email": "user@example.com",
}

REFRESH_TOKEN_PAYLOAD = {
    "email": "user@example.com",
    "user_type": "google",
    "refresh_token_id": str(uuid4()),
    "refresh_token": secrets.token_urlsafe(32),
    "refresh_token_expire_time": (datetime.now() + timedelta(days=1)).isoformat(),
}


def _hash_otp(otp: str) -> str:
    return hmac.new(
        SETTINGS.OTP_SECRET_KEY.encode(), otp.encode(), hashlib.sha256
    ).hexdigest()


def _otp_key(user_id, otp_purpose):
    return f"otp:{user_id!s}:{otp_purpose}"


def _get_otp_payload(email: str, code: str, purpose: str):
    return {
        "email": email,
        "otp_code": code,
        "otp_purpose": purpose,
    }


async def _seed_otp(key, redis: Redis):
    async with redis.pipeline(transaction=True) as pipe:
        pipe.hset(key, mapping={"code": _hash_otp("123456"), "attempts": 0})
        pipe.expire(key, SETTINGS.OTP_EXPIRE_TIME * 60)
        await pipe.execute()


def get_security_mock():
    access_token: str = secrets.token_urlsafe(32)

    security = MagicMock(
        spec=Security()
    )  # pass an instance of the Security class to register instance attributes

    security.prepare_tokens = AsyncMock(
        return_value=(access_token, REFRESH_TOKEN_PAYLOAD)
    )

    return security


def _mock_google_oauth(test: str, security: MagicMock):
    token: dict = {"userinfo": TEST_GOOGLE_PROFILE}

    if test == "redirect":
        security.oauth.google.authorize_redirect = AsyncMock(return_value=None)
    if test == "authorize":
        security.oauth.google.authorize_access_token = AsyncMock(return_value=token)


def _get_token_payload(
    user_id: UUID, iat: datetime | int, expire_time: datetime | int, token_type: str
) -> dict:
    return {
        "iss": SETTINGS.JWT_TOKEN_ISS,
        "sub": str(user_id),
        "exp": expire_time,
        "typ": token_type,
        "iat": iat,
        "jti": str(uuid4()),
        "sid": str(uuid4()),
    }


def _get_test_token(payload: dict, key: str, alg: str | None = None) -> str:
    return jwt.encode(
        {"alg": alg},
        payload,
        OctKey.import_key(key),
    )


def _get_invalid_test_token(header: dict, payload: dict) -> str:
    return (
        base64.urlsafe_b64encode(json.dumps(header).encode(), padded=False).decode()
        + "."
        + base64.urlsafe_b64encode(json.dumps(payload).encode(), padded=False).decode()
        + "."
    )


async def _google_sign_in(async_client: httpx.AsyncClient):
    security = get_security_mock()

    app.dependency_overrides[get_security] = lambda: security

    _mock_google_oauth("redirect", security)
    _mock_google_oauth("authorize", security)

    url_path: str = "app.api.routers.auth.Request.url_for"
    with patch(url_path, new_callable=AsyncMock) as url_patch:
        res: httpx.Response = await async_client.post(
            "/auth/google",
            json={
                "organization_name": "test_org_name",
                "organization_country": "NGA",
            },
        )

        assert res.status_code == 302
        url_patch.assert_called_once()

        res: httpx.Response = await async_client.get("/auth/google/callback")

        assert res.status_code == 200
        assert "access_token" in res.json()["data"]


class TestSignUpWithEmail:
    @pytest.mark.asyncio
    async def test_sign_up(self, create_user: httpx.Response):
        json_res = create_user.json()

        assert create_user.status_code == 201
        assert json_res["message"] == (
            "Sign up completed successfully. "
            "Check your email for verification code and instructions"
        )

    @pytest.mark.asyncio
    async def test_user_exists(
        self, session_maker: async_sessionmaker, async_client: httpx.AsyncClient
    ):
        test_user = await _get_test_user()
        await add_user_to_db(session_maker, test_user.model_dump(), uuid7())

        res: httpx.Response = await async_client.post(
            "/auth/signup", json=_get_signup_payload()
        )

        assert res.status_code == 409

    @pytest.mark.asyncio
    async def test_invalid_email(self, async_client: httpx.AsyncClient):
        sign_up_payload = _get_signup_payload()

        sign_up_payload["email"] = "invalid_user_email"
        res: httpx.Response = await async_client.post(
            "/auth/signup", json=sign_up_payload
        )

        assert res.status_code == 422

        json_res = res.json()
        assert json_res["error"]["code"] == ErrorCode.VALIDATION_ERROR
        assert "body.email" in json_res["error"]["details"]

    @pytest.mark.asyncio
    async def test_invalid_country_code(self, async_client: httpx.AsyncClient):
        sign_up_payload = _get_signup_payload()

        sign_up_payload["organization_country"] = "MXT"
        res: httpx.Response = await async_client.post(
            "/auth/signup", json=sign_up_payload
        )

        assert res.status_code == 422

        json_res = res.json()
        assert json_res["error"]["code"] == ErrorCode.VALIDATION_ERROR
        assert "body.organization_country" in json_res["error"]["details"]

    @pytest.mark.asyncio
    async def test_signup_with_deactivated_email(
        self, session_maker: async_sessionmaker, async_client: httpx.AsyncClient
    ):
        test_user = await _get_test_user()
        test_user.is_active = False

        await add_user_to_db(session_maker, test_user.model_dump(), uuid7())

        res: httpx.Response = await async_client.post(
            "/auth/signup", json=_get_signup_payload()
        )

        assert res.status_code == 409

        json_res = res.json()
        assert json_res["error"]["code"] == ErrorCode.USER_DEACTIVATED


class TestExistingUser:
    @pytest.mark.asyncio
    async def test_link_existing_email_signup(
        self, session_maker: async_sessionmaker, async_client: httpx.AsyncClient
    ):
        test_user = await _get_test_user()
        await add_user_to_db(session_maker, test_user.model_dump(), uuid7())

        await _google_sign_in(async_client)

        user = await get_user_from_db(session_maker, "email", "user@example.com")

        assert user.email
        assert user.hashed_password
        assert user.google_email
        assert user.google_id

    @pytest.mark.asyncio
    async def test_link_unverified_existing_email_signup(
        self, session_maker: async_sessionmaker, async_client: httpx.AsyncClient
    ):
        test_user = await _get_test_user()
        test_user.is_verified = False

        await add_user_to_db(session_maker, test_user.model_dump(), uuid7())

        await _google_sign_in(async_client)

        user = await get_user_from_db(session_maker, "google_email", "user@example.com")

        assert not user.email
        assert not user.hashed_password
        assert user.google_email
        assert user.google_id


class TestRateLimit:
    @pytest.mark.asyncio
    @pytest.mark.rate_limited
    async def test_write_limit_exceeded(self, async_client: httpx.AsyncClient):
        # write_limiter allows 10 requests per window; payload is invalid so
        # nothing is persisted, but each request still counts.
        sign_up_payload: dict = {"email": "invalid_user_email", "password": "x"}

        for _ in range(10):
            res: httpx.Response = await async_client.post(
                "/auth/signup", json=sign_up_payload
            )
            assert res.status_code == 422

        res = await async_client.post("/auth/signup", json=sign_up_payload)

        assert res.status_code == 429

    @pytest.mark.asyncio
    @pytest.mark.rate_limited
    async def test_forwarded_for_does_not_bypass_limit(
        self, async_client: httpx.AsyncClient
    ):
        sign_up_payload: dict = {"email": "invalid_user_email", "password": "x"}

        for i in range(10):
            await async_client.post(
                "/auth/signup",
                json=sign_up_payload,
                headers={"X-Forwarded-For": f"10.0.0.{i}"},
            )

        res: httpx.Response = await async_client.post(
            "/auth/signup",
            json=sign_up_payload,
            headers={"X-Forwarded-For": "10.0.0.99"},
        )

        assert res.status_code == 429


class TestLogin:
    @pytest.mark.asyncio
    async def test_login(self, async_client: httpx.AsyncClient, login: httpx.Response):
        json_res = login.json()

        assert login.status_code == 201
        assert "access_token" in json_res["data"]

    @pytest.mark.asyncio
    async def test_user_not_verified(
        self, async_client: httpx.AsyncClient, create_user: httpx.Response
    ):
        res: httpx.Response = await async_client.post(
            "/auth/login",
            json={
                "email": "user@example.com",
                "password": "test_user_password",
            },
        )

        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_wrong_email_login(
        self, session_maker: async_sessionmaker, async_client: httpx.AsyncClient
    ):
        test_user = await _get_test_user()
        await add_user_to_db(session_maker, test_user.model_dump(), uuid7())

        res: httpx.Response = await async_client.post(
            "/auth/login",
            json={
                "email": "user@example123.com",
                "password": "test_user_password",
            },
        )

        assert res.status_code == 400


class TestSignUpWithGoogle:
    @pytest.mark.asyncio
    async def test_google_sign_in(self, async_client: httpx.AsyncClient):
        await _google_sign_in(async_client)


class TestAuthToken:
    @pytest.mark.asyncio
    async def test_refresh_access_token(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        res = await async_client.post(
            "/auth/refresh",
        )
        json_res = res.json()

        assert res.status_code == 201
        assert "access_token" in json_res["data"]

    @pytest.mark.asyncio
    async def test_expired_access_token(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        test_user = await _get_test_user()
        expire_time: datetime = datetime.now(UTC) - timedelta(
            minutes=SETTINGS.ACCESS_TOKEN_EXPIRE_TIME
        )

        token = _get_test_token(
            _get_token_payload(test_user.id, datetime.now(UTC), expire_time, "access"),
            SETTINGS.ACCESS_TOKEN_SECRET_KEY,
            SETTINGS.JWT_ALGORITHM,
        )

        res: httpx.Response = await async_client.get(
            "/auth/me",
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        assert res.status_code == 401
        assert res.json()["error"]["details"]["reason"] == "Access Token Expired"

    @pytest.mark.asyncio
    async def test_unauthorized_refresh_access_token(
        self, async_client: httpx.AsyncClient
    ):
        res = await async_client.post(
            "/auth/refresh",
        )

        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_token_used_as_access_token(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        test_user = await _get_test_user()
        expire_time: datetime = datetime.now(UTC) + timedelta(
            days=SETTINGS.REFRESH_TOKEN_EXPIRE_TIME
        )
        token = _get_test_token(
            _get_token_payload(test_user.id, datetime.now(UTC), expire_time, "refresh"),
            SETTINGS.ACCESS_TOKEN_SECRET_KEY,
            SETTINGS.JWT_ALGORITHM,
        )

        res: httpx.Response = await async_client.get(
            "/auth/me",
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        assert res.status_code == 401
        assert res.json()["error"]["details"]["reason"] == "Invalid Access Token"

    @pytest.mark.asyncio
    async def test_token_with_invalid_algorithm(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        test_user = await _get_test_user()
        expire_time: int = int(
            (
                datetime.now(UTC) + timedelta(minutes=SETTINGS.ACCESS_TOKEN_EXPIRE_TIME)
            ).timestamp()
        )

        token = _get_invalid_test_token(
            {"alg": "none", "typ": "JWT"},
            _get_token_payload(
                test_user.id,
                int(datetime.now(UTC).timestamp()),
                expire_time,
                "access",
            ),
        )

        res: httpx.Response = await async_client.get(
            "/auth/me",
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        assert res.status_code == 401
        assert res.json()["error"]["details"]["reason"] == "Invalid Access Token"

    @pytest.mark.asyncio
    async def test_detect_refresh_token_reuse(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        res = await async_client.post(
            "/auth/refresh",
        )
        used_refresh_token = res.cookies.get("refresh_token")

        res = await async_client.post(
            "/auth/refresh",
        )

        new_refresh_token = res.cookies.get("refresh_token")

        assert res.status_code == 201

        # confirm reuse is detected after second refresh used the same refresh token
        async_client.cookies.set("refresh_token", used_refresh_token)

        res = await async_client.post(
            "/auth/refresh",
        )

        assert res.status_code == 401
        assert res.json()["error"]["details"]["reason"] == "Refresh Token Used"

        # confirm the session is killed and the user is forced to re-authenticate
        async_client.cookies.set("refresh_token", new_refresh_token)

        res = await async_client.post(
            "/auth/refresh",
        )

        assert res.status_code == 401
        assert res.json()["error"]["details"]["reason"] == "Invalid Refresh Token"

    @pytest.mark.asyncio
    async def test_reject_tampered_token(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        original_token = login.json()["data"]["access_token"]

        decoded_token = original_token.split(".")

        claims = json.loads(
            base64.urlsafe_b64decode(decoded_token[1], padded=False).decode()
        )
        claims["sub"] = str(uuid4())

        decoded_token[1] = base64.urlsafe_b64encode(
            json.dumps(claims).encode(), padded=False
        ).decode()
        token = decoded_token[0] + "." + decoded_token[1] + "." + decoded_token[2]

        res: httpx.Response = await async_client.get(
            "/auth/me",
            headers={
                "Authorization": f"Bearer {token}",
            },
        )

        assert res.status_code == 401
        assert res.json()["error"]["details"]["reason"] == "Invalid Access Token"


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_get_current_user(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        access_token = login.json()["data"]["access_token"]

        res: httpx.Response = await async_client.get(
            "/auth/me",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        json_res = res.json()

        assert res.status_code == 200
        assert "user@example.com" == json_res["data"]["email"]

    @pytest.mark.asyncio
    async def test_unauthenticated_user(self, async_client: httpx.AsyncClient):
        res: httpx.Response = await async_client.get(
            "/auth/me",
        )

        assert res.status_code == 401


class TestVerifyOtp:
    @pytest.mark.asyncio
    async def test_verify_valid_otp(
        self,
        session_maker: async_sessionmaker,
        async_client: httpx.AsyncClient,
        test_redis_client: Redis,
    ):
        test_user = await _get_test_user()

        await add_user_to_db(session_maker, test_user.model_dump(), uuid7())
        await _seed_otp(_otp_key(test_user.id, "email_verification"), test_redis_client)

        res: httpx.Response = await async_client.patch(
            "/auth/verify",
            json=_get_otp_payload("user@example.com", "123456", "email_verification"),
        )

        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_verify_invalid_otp(
        self,
        session_maker: async_sessionmaker,
        async_client: httpx.AsyncClient,
        test_redis_client: Redis,
    ):
        test_user = await _get_test_user()

        await add_user_to_db(session_maker, test_user.model_dump(), uuid7())
        await _seed_otp(_otp_key(test_user.id, "email_verification"), test_redis_client)

        res: httpx.Response = await async_client.patch(
            "/auth/verify",
            json=_get_otp_payload("user@example.com", "123455", "email_verification"),
        )

        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_verify_otp_max_attempts_exceeded(
        self,
        session_maker: async_sessionmaker,
        async_client: httpx.AsyncClient,
        test_redis_client: Redis,
    ):
        test_user = await _get_test_user()

        await add_user_to_db(session_maker, test_user.model_dump(), uuid7())
        await _seed_otp(_otp_key(test_user.id, "email_verification"), test_redis_client)

        for _ in range(SETTINGS.OTP_MAX_ATTEMPTS):
            res: httpx.Response = await async_client.patch(
                "/auth/verify",
                json=_get_otp_payload(
                    "user@example.com", "123455", "email_verification"
                ),
            )

        assert res.status_code == 400
        assert res.json()["error"]["code"] == "OTP_ATTEMPTS_EXCEEDED"


class TestLogout:
    @pytest.mark.asyncio
    async def test_logout(self, async_client: httpx.AsyncClient, login: httpx.Response):
        access_token = login.json()["data"]["access_token"]

        res = await async_client.post(
            "/auth/logout",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert res.status_code == 201

    @pytest.mark.asyncio
    async def test_unauthorized_logout(
        self, session_maker: async_sessionmaker, async_client: httpx.AsyncClient
    ):
        test_user = await _get_test_user()

        await add_user_to_db(session_maker, test_user.model_dump(), uuid7())
        res = await async_client.post(
            "/auth/logout",
        )

        assert res.status_code == 401


class TestDeactivateAccount:
    @pytest.mark.asyncio
    async def test_deactivate_account(
        self, async_client: httpx.AsyncClient, login: httpx.Response
    ):
        access_token = login.json()["data"]["access_token"]

        res = await async_client.delete(
            "/auth/deactivate",
            headers={
                "Authorization": f"Bearer {access_token}",
            },
        )

        assert res.status_code == 204

        res: httpx.Response = await async_client.post(
            "/auth/login",
            json={
                "email": "user@example.com",
                "password": "test_user_password",
            },
        )

        assert res.status_code == 400

    @pytest.mark.asyncio
    async def test_unauthorized_deactivate_account(
        self, session_maker: async_sessionmaker, async_client: httpx.AsyncClient
    ):
        test_user = await _get_test_user()

        await add_user_to_db(session_maker, test_user.model_dump(), uuid7())
        res = await async_client.delete(
            "/auth/deactivate",
        )

        assert res.status_code == 401


class TestResendOtp:
    @pytest.mark.asyncio
    async def test_resend_otp_token(
        self,
        session_maker: async_sessionmaker,
        async_client: httpx.AsyncClient,
    ):
        test_user = await _get_test_user()
        test_user.is_verified = False

        await add_user_to_db(session_maker, test_user.model_dump(), uuid7())

        path: str = "app.api.services.auth.send_email.apply_async"

        with patch(path) as email_patch:
            res: httpx.Response = await async_client.post(
                "/auth/verify/resend",
                json={
                    "email": "user@example.com",
                    "otp_purpose": "email_verification",
                },
            )

        json_res = res.json()

        email_patch.assert_called_once()

        assert res.status_code == 201
        assert json_res["status"] == "success"

    @pytest.mark.asyncio
    async def test_invalid_email_otp_token(
        self,
        session_maker: async_sessionmaker,
        async_client: httpx.AsyncClient,
    ):
        test_user = await _get_test_user()
        test_user.is_verified = False

        await add_user_to_db(session_maker, test_user.model_dump(), uuid7())

        path: str = "app.api.services.auth.send_email.apply_async"

        with patch(path) as email_patch:
            res: httpx.Response = await async_client.post(
                "/auth/verify/resend",
                json={
                    "email": "user@example123.com",
                    "otp_purpose": "email_verification",
                },
            )

        assert res.status_code == 201
        email_patch.assert_not_called()


class TestReactivateAccount:
    @pytest.mark.asyncio
    async def test_reactivate_account(
        self,
        session_maker: async_sessionmaker,
        async_client: httpx.AsyncClient,
        test_redis_client: Redis,
    ):
        test_user = await _get_test_user()
        test_user.is_active = False

        await add_user_to_db(session_maker, test_user.model_dump(), uuid7())

        path: str = "app.api.services.auth.send_email.apply_async"

        with patch(path) as email_patch:
            res = await async_client.patch(
                "/auth/reactivate", json={"email": "user@example.com"}
            )

        assert res.status_code == 200
        email_patch.assert_called_once()

        await _seed_otp(
            _otp_key(test_user.id, "account_reactivation"), test_redis_client
        )

        res: httpx.Response = await async_client.patch(
            "/auth/verify",
            json=_get_otp_payload("user@example.com", "123456", "account_reactivation"),
        )

        assert res.status_code == 200

        res: httpx.Response = await async_client.post(
            "/auth/login",
            json={
                "email": "user@example.com",
                "password": "test_user_password",
            },
        )

        assert res.status_code == 201
        assert "access_token" in res.json()["data"]

    @pytest.mark.asyncio
    async def test_reactivate_account_with_invalid_email(
        self, async_client: httpx.AsyncClient
    ):
        path: str = "app.api.services.auth.send_email.apply_async"

        with patch(path) as email_patch:
            res = await async_client.patch(
                "/auth/reactivate", json={"email": "userinvalid@example.com"}
            )

        assert res.status_code == 200
        email_patch.assert_not_called()

    @pytest.mark.asyncio
    async def test_reactivate_active_account(
        self,
        session_maker: async_sessionmaker,
        async_client: httpx.AsyncClient,
        test_redis_client: Redis,
    ):
        test_user = await _get_test_user()
        await add_user_to_db(session_maker, test_user.model_dump(), uuid7())

        path: str = "app.api.services.auth.send_email.apply_async"

        with patch(path) as email_patch:
            res = await async_client.patch(
                "/auth/reactivate", json={"email": "user@example.com"}
            )

        assert res.status_code == 200
        email_patch.assert_not_called()
