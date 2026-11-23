from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4, uuid7

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.models.invite import Invite
from app.api.models.user import User
from app.core.enum import ErrorCode, InviteStatus
from test.conftest import (
    _login_user,
    add_employee_to_db,
    add_invite_to_db,
    add_user,
)

EMAIL_PATCH = "app.api.services.email.send_email.apply_async"


async def _get_invite(session_maker: async_sessionmaker, invite_id) -> Invite | None:
    async with session_maker() as session:
        return await session.scalar(select(Invite).where(Invite.id == invite_id))


class TestCreateInvite:
    @pytest.mark.asyncio
    async def test_create_invite(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())
        employee = await add_employee_to_db(session_maker, user["organization_id"])

        with patch(EMAIL_PATCH):
            res = await async_client.post(
                "/invites",
                headers=await _login_user(async_client, user),
                json={"employee_id": str(employee["id"])},
            )

        assert res.status_code == 201
        data = res.json()["data"]
        assert data["employee_id"] == str(employee["id"])
        assert data["status"] == InviteStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_create_invite_when_active_exists(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())
        employee = await add_employee_to_db(session_maker, user["organization_id"])
        await add_invite_to_db(session_maker, employee, user["id"])

        res = await async_client.post(
            "/invites",
            headers=await _login_user(async_client, user),
            json={"employee_id": str(employee["id"])},
        )

        assert res.status_code == 409
        assert res.json()["error"]["code"] == ErrorCode.INVITE_EXISTS

    @pytest.mark.asyncio
    async def test_create_invite_employee_not_found(
        self,
        async_client: httpx.AsyncClient,
        admin_user,
    ):
        user = await admin_user(uuid7())

        res = await async_client.post(
            "/invites",
            headers=await _login_user(async_client, user),
            json={"employee_id": str(uuid4())},
        )

        assert res.status_code == 404
        assert res.json()["error"]["code"] == ErrorCode.NOT_FOUND


class TestGetInvites:
    @pytest.mark.asyncio
    async def test_get_invites(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())
        employee = await add_employee_to_db(session_maker, user["organization_id"])
        await add_invite_to_db(session_maker, employee, user["id"])

        res = await async_client.get(
            "/invites?limit=10",
            headers=await _login_user(async_client, user),
        )

        assert res.status_code == 200
        assert len(res.json()["data"]) == 1

    @pytest.mark.asyncio
    async def test_get_invite(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())
        employee = await add_employee_to_db(session_maker, user["organization_id"])
        invite = await add_invite_to_db(session_maker, employee, user["id"])

        res = await async_client.get(
            f"/invites/{invite['id']}",
            headers=await _login_user(async_client, user),
        )

        assert res.status_code == 200
        assert res.json()["data"]["id"] == str(invite["id"])

    @pytest.mark.asyncio
    async def test_get_invite_not_found(
        self,
        async_client: httpx.AsyncClient,
        admin_user,
    ):
        user = await admin_user(uuid7())

        res = await async_client.get(
            f"/invites/{uuid4()}",
            headers=await _login_user(async_client, user),
        )

        assert res.status_code == 404
        assert res.json()["error"]["code"] == ErrorCode.NOT_FOUND


class TestAcceptInvite:
    @pytest.mark.asyncio
    async def test_accept_invite(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())
        employee = await add_employee_to_db(session_maker, user["organization_id"])
        invite = await add_invite_to_db(session_maker, employee, user["id"])

        res = await async_client.patch(
            "/invites/accept",
            json={"token": invite["token"], "password": "password123"},
        )

        assert res.status_code == 200

        db_invite = await _get_invite(session_maker, invite["id"])
        assert db_invite.status == InviteStatus.USED
        assert db_invite.used_at is not None

        async with session_maker() as session:
            db_user = await session.scalar(
                select(User).where(User.employee_id == employee["id"])
            )
        assert db_user is not None
        assert db_user.email == employee["email"]

    @pytest.mark.asyncio
    async def test_accept_invite_not_found(self, async_client: httpx.AsyncClient):
        res = await async_client.patch(
            "/invites/accept",
            json={"token": "missing-token", "password": "password123"},
        )

        assert res.status_code == 404
        assert res.json()["error"]["code"] == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_accept_expired_invite(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())
        employee = await add_employee_to_db(session_maker, user["organization_id"])
        invite = await add_invite_to_db(
            session_maker,
            employee,
            user["id"],
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )

        res = await async_client.patch(
            "/invites/accept",
            json={"token": invite["token"], "password": "password123"},
        )

        assert res.status_code == 410
        assert res.json()["error"]["code"] == ErrorCode.INVITE_EXPIRED

    @pytest.mark.asyncio
    async def test_accept_invite_when_user_exists(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())
        email = "existing_employee@example.com"
        employee = await add_employee_to_db(
            session_maker, user["organization_id"], email=email
        )
        await add_user(
            user["organization_id"], session_maker, email=email, role_key="employee"
        )
        invite = await add_invite_to_db(session_maker, employee, user["id"])

        res = await async_client.patch(
            "/invites/accept",
            json={"token": invite["token"], "password": "password123"},
        )

        assert res.status_code == 409
        assert res.json()["error"]["code"] == ErrorCode.INVITE_USER_EXISTS


class TestRejectInvite:
    @pytest.mark.asyncio
    async def test_reject_invite(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())
        employee = await add_employee_to_db(session_maker, user["organization_id"])
        invite = await add_invite_to_db(session_maker, employee, user["id"])

        res = await async_client.patch(
            "/invites/reject",
            json={"token": invite["token"]},
        )

        assert res.status_code == 200

        db_invite = await _get_invite(session_maker, invite["id"])
        assert db_invite.status == InviteStatus.REJECTED

    @pytest.mark.asyncio
    async def test_reject_expired_invite(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())
        employee = await add_employee_to_db(session_maker, user["organization_id"])
        invite = await add_invite_to_db(
            session_maker,
            employee,
            user["id"],
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )

        res = await async_client.patch(
            "/invites/reject",
            json={"token": invite["token"]},
        )

        assert res.status_code == 410
        assert res.json()["error"]["code"] == ErrorCode.INVITE_EXPIRED
