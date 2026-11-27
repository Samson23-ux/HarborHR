from datetime import date, timedelta
from uuid import uuid4, uuid7

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.models.statutory_rules import StatutoryRule
from app.core.enum import ErrorCode
from test.conftest import (
    _login_user,
    add_statutory_rule_to_db,
    add_user,
)

RULES_PATH = "/statutory-rules"


def _future_date(days: int = 30) -> date:
    return date.today() + timedelta(days=days)


def _rule_payload(effective_from: date | None = None) -> dict:
    return {
        "relief": "200000.00",
        "relief_percentage": "0.2",
        "employee_pension_rate": "8.0",
        "employer_pension_rate": "10.0",
        "tax_bands": {"bands": [{"limit": "300000", "rate": "7"}]},
        "effective_from": (effective_from or _future_date()).isoformat(),
    }


async def _staff_user(session_maker: async_sessionmaker) -> dict:
    return await add_user(
        uuid7(),
        session_maker,
        role_key="staff",
        email=f"staff_{uuid4().hex[:8]}@example.com",
    )


class TestCreateStatutoryRule:
    @pytest.mark.asyncio
    async def test_create_statutory_rule(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
    ):
        user = await _staff_user(session_maker)
        payload = _rule_payload()

        res = await async_client.post(
            RULES_PATH,
            headers=await _login_user(async_client, user),
            json=payload,
        )

        assert res.status_code == 201
        data = res.json()["data"]
        assert data["effective_from"] == payload["effective_from"]
        assert data["version"] == 1
        assert data["created_by"] == str(user["id"])

        async with session_maker() as session:
            db_rule = await session.scalar(
                select(StatutoryRule).where(StatutoryRule.id == data["id"])
            )
        assert db_rule is not None
        assert db_rule.version == 1

    @pytest.mark.asyncio
    async def test_create_statutory_rule_increments_version(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
    ):
        user = await _staff_user(session_maker)
        headers = await _login_user(async_client, user)
        effective_from = _future_date()

        first = await async_client.post(
            RULES_PATH, headers=headers, json=_rule_payload(effective_from)
        )
        second = await async_client.post(
            RULES_PATH, headers=headers, json=_rule_payload(effective_from)
        )

        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["data"]["version"] == 1
        assert second.json()["data"]["version"] == 2

    @pytest.mark.asyncio
    async def test_create_statutory_rule_with_past_effective_from(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
    ):
        user = await _staff_user(session_maker)

        res = await async_client.post(
            RULES_PATH,
            headers=await _login_user(async_client, user),
            json=_rule_payload(date.today() - timedelta(days=1)),
        )

        assert res.status_code == 422
        assert res.json()["error"]["code"] == ErrorCode.VALIDATION_ERROR

    @pytest.mark.asyncio
    async def test_create_statutory_rule_not_permitted(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        employee_user,
    ):
        user = await employee_user(uuid7())

        res = await async_client.post(
            RULES_PATH,
            headers=await _login_user(async_client, user),
            json=_rule_payload(),
        )

        assert res.status_code == 403
        assert res.json()["error"]["code"] == ErrorCode.NOT_PERMITTED


class TestGetStatutoryRules:
    @pytest.mark.asyncio
    async def test_get_statutory_rules(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
    ):
        user = await _staff_user(session_maker)
        await add_statutory_rule_to_db(session_maker, user["id"], _future_date())

        res = await async_client.get(
            f"{RULES_PATH}?limit=10",
            headers=await _login_user(async_client, user),
        )

        assert res.status_code == 200
        body = res.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["effective_from"] == _future_date().isoformat()

    @pytest.mark.asyncio
    async def test_get_statutory_rules_when_empty(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
    ):
        user = await _staff_user(session_maker)

        res = await async_client.get(
            RULES_PATH,
            headers=await _login_user(async_client, user),
        )

        assert res.status_code == 404
        assert res.json()["error"]["code"] == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_statutory_rules_pagination(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
    ):
        user = await _staff_user(session_maker)
        await add_statutory_rule_to_db(
            session_maker, user["id"], _future_date(30), version=1
        )
        await add_statutory_rule_to_db(
            session_maker, user["id"], _future_date(31), version=2
        )

        res = await async_client.get(
            f"{RULES_PATH}?limit=1",
            headers=await _login_user(async_client, user),
        )

        assert res.status_code == 200
        body = res.json()
        assert len(body["data"]) == 1
        assert body["cursor"] is not None

        next_res = await async_client.get(
            f"{RULES_PATH}?limit=1&cursor={body['cursor']}",
            headers=await _login_user(async_client, user),
        )

        assert next_res.status_code == 200
        assert len(next_res.json()["data"]) == 1
        assert next_res.json()["data"][0]["id"] != body["data"][0]["id"]

    @pytest.mark.asyncio
    async def test_get_statutory_rule(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
    ):
        user = await _staff_user(session_maker)
        rule = await add_statutory_rule_to_db(
            session_maker, user["id"], _future_date()
        )

        res = await async_client.get(
            f"{RULES_PATH}/{rule['id']}",
            headers=await _login_user(async_client, user),
        )

        assert res.status_code == 200
        assert res.json()["data"]["id"] == str(rule["id"])

    @pytest.mark.asyncio
    async def test_get_statutory_rule_not_found(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
    ):
        user = await _staff_user(session_maker)

        res = await async_client.get(
            f"{RULES_PATH}/{uuid4()}",
            headers=await _login_user(async_client, user),
        )

        assert res.status_code == 404
        assert res.json()["error"]["code"] == ErrorCode.NOT_FOUND
