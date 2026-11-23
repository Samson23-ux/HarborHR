from datetime import date
from uuid import uuid4, uuid7

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.enum import ErrorCode
from test.conftest import (
    _login_user,
    add_employee_to_db,
    add_employment_period_to_db,
    add_pay_to_db,
)


def _employee_payload(organization_id, **overrides) -> dict:
    payload = {
        "first_name": "Jane",
        "last_name": "Doe",
        "organization_id": str(organization_id),
        "email": f"created_{uuid4().hex[:8]}@example.com",
        "role": "employee",
        "employment_period": {"start_date": "2024-01-01"},
        "employee_pay": {
            "basic": "500000.00",
            "housing": "100000.00",
            "transport": "50000.00",
            "effective_from": "2024-01-01",
        },
    }
    payload.update(overrides)
    return payload


def _pay_payload(effective_from: str = "2024-02-01") -> dict:
    return {
        "basic": "600000.00",
        "housing": "120000.00",
        "transport": "60000.00",
        "effective_from": effective_from,
    }


class TestOrganization:
    @pytest.mark.asyncio
    async def test_get_organization(self, async_client: httpx.AsyncClient, admin_user):
        user = await admin_user(uuid7())
        organization_id = user["organization_id"]

        res = await async_client.get(
            f"/organization/{organization_id}",
            headers=await _login_user(async_client, user),
        )

        assert res.status_code == 200
        assert res.json()["data"]["id"] == str(organization_id)

    @pytest.mark.asyncio
    async def test_get_organization_not_member(
        self, async_client: httpx.AsyncClient, admin_user, employee_user
    ):
        _admin_user = await admin_user(uuid7())
        _employee_user = await employee_user(uuid7())

        res = await async_client.get(
            f"/organization/{_admin_user['organization_id']}",
            headers=await _login_user(async_client, _employee_user),
        )

        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_update_organization(
        self, async_client: httpx.AsyncClient, admin_user
    ):
        user = await admin_user(uuid7())
        organization_id = user["organization_id"]

        res = await async_client.patch(
            f"/organization/{organization_id}",
            headers=await _login_user(async_client, user),
            json={"name": "Updated Org"},
        )

        assert res.status_code == 200
        assert res.json()["data"]["name"] == "Updated Org"

    @pytest.mark.asyncio
    async def test_update_organization_requires_admin(
        self, async_client: httpx.AsyncClient, admin_user, employee_user
    ):
        org_id = uuid7()

        _ = await admin_user(org_id)
        _employee_user = await employee_user(org_id)

        res = await async_client.patch(
            f"/organization/{uuid4()}",
            headers=await _login_user(async_client, _employee_user),
            json={"name": "Nope"},
        )

        assert res.status_code == 403


class TestEmployee:
    @pytest.mark.asyncio
    async def test_create_employee(self, async_client: httpx.AsyncClient, admin_user):
        user = await admin_user(uuid7())

        res = await async_client.post(
            "/employees",
            headers=await _login_user(async_client, user),
            json=_employee_payload(user["organization_id"]),
        )

        assert res.status_code == 201
        data = res.json()["data"]
        assert data["first_name"] == "Jane"
        assert data["role"] == "employee"
        assert data["employment_period"][0]["start_date"] == "2024-01-01"
        assert data["employee_pay"][0]["version"] == 1

    @pytest.mark.asyncio
    async def test_create_employee_duplicate_email(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())

        email = "duplicate@example.com"
        await add_employee_to_db(session_maker, user["organization_id"], email=email)

        res = await async_client.post(
            "/employees",
            headers=await _login_user(async_client, user),
            json=_employee_payload(user["organization_id"], email=email),
        )

        assert res.status_code == 409
        assert res.json()["error"]["code"] == ErrorCode.EMPLOYEE_EXISTS

    @pytest.mark.asyncio
    async def test_get_employee_with_details(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())

        employee = await add_employee_to_db(session_maker, user["organization_id"])
        await add_employment_period_to_db(session_maker, employee, date(2024, 1, 1))
        await add_pay_to_db(session_maker, employee, user["id"], date(2024, 1, 1))

        res = await async_client.get(
            f"/employees/{employee['id']}?details=true",
            headers=await _login_user(async_client, user),
        )

        assert res.status_code == 200
        data = res.json()["data"]
        assert data["id"] == str(employee["id"])
        assert len(data["employment_period"]) == 1
        assert len(data["employee_pay"]) == 1

    @pytest.mark.asyncio
    async def test_get_employee_not_found(
        self,
        async_client: httpx.AsyncClient,
        admin_user,
    ):
        user = await admin_user(uuid7())

        res = await async_client.get(
            f"/employees/{uuid4()}?details=false",
            headers=await _login_user(async_client, user),
        )

        assert res.status_code == 404
        assert res.json()["error"]["code"] == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_employees(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())

        await add_employee_to_db(session_maker, user["organization_id"])
        await add_employee_to_db(session_maker, user["organization_id"])

        res = await async_client.get(
            "/employees?limit=10",
            headers=await _login_user(async_client, user),
        )

        assert res.status_code == 200
        assert len(res.json()["data"]) == 2

    @pytest.mark.asyncio
    async def test_search_employees(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())

        await add_employee_to_db(
            session_maker, user["organization_id"], first_name="Searchable"
        )

        res = await async_client.get(
            "/employees/search?q=Searchable&limit=10",
            headers=await _login_user(async_client, user),
        )

        assert res.status_code == 200
        assert len(res.json()["data"]) == 1

    @pytest.mark.asyncio
    async def test_update_employee(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())
        employee = await add_employee_to_db(session_maker, user["organization_id"])

        res = await async_client.patch(
            f"/employees/{employee['id']}",
            headers=await _login_user(async_client, user),
            json={"first_name": "Updated"},
        )

        assert res.status_code == 200
        assert res.json()["data"]["first_name"] == "Updated"

    @pytest.mark.asyncio
    async def test_deactivate_and_reactivate_employee(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())
        employee = await add_employee_to_db(session_maker, user["organization_id"])

        headers = await _login_user(async_client, user)

        deactivate = await async_client.delete(
            f"/employees/{employee['id']}/deactivate",
            headers=headers,
        )
        assert deactivate.status_code == 204

        get_inactive = await async_client.get(
            f"/employees/{employee['id']}?details=false",
            headers=headers,
        )
        assert get_inactive.status_code == 404

        reactivate = await async_client.patch(
            f"/employees/{employee['id']}/reactivate",
            headers=headers,
        )
        assert reactivate.status_code == 200
        assert reactivate.json()["data"]["is_active"] is True


class TestEmployeePay:
    @pytest.mark.asyncio
    async def test_create_pay(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())
        employee = await add_employee_to_db(session_maker, user["organization_id"])

        res = await async_client.post(
            f"/employees/{employee['id']}/pay",
            headers=await _login_user(async_client, user),
            json=_pay_payload(),
        )

        assert res.status_code == 201
        data = res.json()["data"]
        assert data["employee_id"] == str(employee["id"])
        assert data["version"] == 1
        assert data["created_by"] == str(user["id"])

    @pytest.mark.asyncio
    async def test_create_pay_increments_version(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())
        employee = await add_employee_to_db(session_maker, user["organization_id"])

        headers = await _login_user(async_client, user)

        await async_client.post(
            f"/employees/{employee['id']}/pay",
            headers=headers,
            json=_pay_payload("2024-02-01"),
        )
        res = await async_client.post(
            f"/employees/{employee['id']}/pay",
            headers=headers,
            json=_pay_payload("2024-03-01"),
        )

        assert res.status_code == 201
        assert res.json()["data"]["version"] == 2

    @pytest.mark.asyncio
    async def test_create_pay_invalid_body(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())
        employee = await add_employee_to_db(session_maker, user["organization_id"])

        res = await async_client.post(
            f"/employees/{employee['id']}/pay",
            headers=await _login_user(async_client, user),
            json={"effective_from": "2024-01-01"},
        )

        assert res.status_code == 422


class TestEmploymentPeriod:
    @pytest.mark.asyncio
    async def test_create_period(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())
        employee = await add_employee_to_db(session_maker, user["organization_id"])

        res = await async_client.post(
            f"/employees/{employee['id']}/employment-period",
            headers=await _login_user(async_client, user),
            json={"start_date": "2024-01-01"},
        )

        assert res.status_code == 201
        assert res.json()["data"]["start_date"] == "2024-01-01"

    @pytest.mark.asyncio
    async def test_create_period_when_active_exists(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())

        employee = await add_employee_to_db(session_maker, user["organization_id"])
        await add_employment_period_to_db(session_maker, employee, date(2024, 1, 1))

        res = await async_client.post(
            f"/employees/{employee['id']}/employment-period",
            headers=await _login_user(async_client, user),
            json={"start_date": "2024-06-01"},
        )

        assert res.status_code == 409
        assert res.json()["error"]["code"] == ErrorCode.ACTIVE_EMPLOYMENT_PERIOD

    @pytest.mark.asyncio
    async def test_create_period_overlaps_latest(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())

        employee = await add_employee_to_db(session_maker, user["organization_id"])
        await add_employment_period_to_db(
            session_maker, employee, date(2024, 1, 1), date(2024, 6, 1)
        )

        res = await async_client.post(
            f"/employees/{employee['id']}/employment-period",
            headers=await _login_user(async_client, user),
            json={"start_date": "2024-05-01", "end_date": "2024-07-01"},
        )

        assert res.status_code == 400
        assert res.json()["error"]["code"] == ErrorCode.INVALID_EMPLOYMENT_PERIOD

    @pytest.mark.asyncio
    async def test_update_period(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())

        employee = await add_employee_to_db(session_maker, user["organization_id"])
        await add_employment_period_to_db(session_maker, employee, date(2024, 1, 1))

        res = await async_client.patch(
            f"/employees/{employee['id']}/employment-period",
            headers=await _login_user(async_client, user),
            json={"end_date": "2024-06-01"},
        )

        assert res.status_code == 200
        assert res.json()["data"]["end_date"] == "2024-06-01"

    @pytest.mark.asyncio
    async def test_update_period_not_found(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())

        employee = await add_employee_to_db(session_maker, user["organization_id"])
        await add_employment_period_to_db(
            session_maker, employee, date(2024, 1, 1), date(2024, 6, 1)
        )

        res = await async_client.patch(
            f"/employees/{employee['id']}/employment-period",
            headers=await _login_user(async_client, user),
            json={"end_date": "2024-07-01"},
        )

        assert res.status_code == 404
        assert res.json()["error"]["code"] == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_period_end_before_start(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        user = await admin_user(uuid7())

        employee = await add_employee_to_db(session_maker, user["organization_id"])
        await add_employment_period_to_db(session_maker, employee, date(2024, 5, 1))

        res = await async_client.patch(
            f"/employees/{employee['id']}/employment-period",
            headers=await _login_user(async_client, user),
            json={"end_date": "2024-04-01"},
        )

        assert res.status_code == 400
        assert res.json()["error"]["code"] == ErrorCode.INVALID_EMPLOYMENT_PERIOD


class TestOrganizationIsolation:
    @pytest.mark.asyncio
    async def test_organization_isolation(
        self,
        async_client: httpx.AsyncClient,
        session_maker: async_sessionmaker,
        admin_user,
    ):
        admin_1 = await admin_user(uuid7())
        admin_2 = await admin_user(uuid7())

        employee = await add_employee_to_db(session_maker, admin_1["organization_id"])

        res = await async_client.patch(
            f"/employees/{employee['id']}",
            headers=await _login_user(async_client, admin_2),
            json={"first_name": "Updated"},
        )

        assert res.status_code == 404
        assert res.json()["error"]["code"] == ErrorCode.NOT_FOUND
