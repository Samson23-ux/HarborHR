import secrets
from collections.abc import AsyncGenerator, Awaitable
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import UUID, uuid4, uuid7

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient, Response
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    AsyncTransaction,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.api import models  # noqa: F401
from app.api.models.base import Base
from app.api.models.employee import Employee, EmployeePay, EmploymentPeriod
from app.api.models.invite import Invite
from app.api.models.organization import Organization
from app.api.models.role import Role as DbRole
from app.api.models.user import User
from app.api.schemas.user import UserInDB
from app.core.config import get_settings
from app.core.enum import InviteStatus, Role
from app.core.security import Security
from app.database.session import get_session
from app.deps import (
    get_redis_client,
    read_limiter,
    write_limiter,
)
from app.main import app

SECURITY = Security()
SETTINGS = get_settings()


async def prepare_database(conn: AsyncConnection):
    await conn.execute(
        text(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{SETTINGS.DB_TEST_USER}') THEN
                    CREATE ROLE {SETTINGS.DB_TEST_USER} LOGIN PASSWORD '{SETTINGS.DB_TEST_PASSWORD}'
                        NOSUPERUSER NOBYPASSRLS;
                END IF;
            END $$;
        """)
    )
    await conn.execute(
        text(f"""
            GRANT CONNECT ON DATABASE {SETTINGS.DB_TEST} TO {SETTINGS.DB_TEST_USER};
        """)
    )

    await conn.execute(
        text(f"GRANT USAGE ON SCHEMA public TO {SETTINGS.DB_TEST_USER};")
    )

    await conn.execute(
        text(f"""
            ALTER DEFAULT PRIVILEGES FOR ROLE {SETTINGS.DB_OWNER_ROLE} IN SCHEMA public
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {SETTINGS.DB_TEST_USER};
        """)
    )

    await conn.execute(
        text("""
            CREATE OR REPLACE FUNCTION uuid_generate_v7()
                RETURNS UUID
                LANGUAGE SQL
                VOLATILE
                AS $$
                    SELECT encode(
                        set_bit(
                            set_bit(
                                overlay(
                                    uuid_send(gen_random_uuid())
                                    placing substring(int8send(floor(extract(epoch FROM clock_timestamp()) * 1000)::bigint) FROM 3)
                                    FROM 1 FOR 6
                                ),
                                52, 1
                            ),
                            53, 1
                        ),
                        'hex'
                    )::uuid
                $$;
        """)
    )

    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist;"))
    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
    await conn.run_sync(Base.metadata.create_all)


async def clean_database(conn: AsyncConnection):
    await conn.execute(text("DROP FUNCTION IF EXISTS uuid_generate_v7 CASCADE;"))
    await conn.execute(text("DROP EXTENSION IF EXISTS pgcrypto CASCADE;"))
    await conn.run_sync(Base.metadata.drop_all)
    await conn.execute(text("DROP EXTENSION IF EXISTS btree_gist;"))
    await conn.execute(text("DROP EXTENSION IF EXISTS pg_trgm;"))


@pytest_asyncio.fixture(scope="session")
async def async_engine():
    migration_db_engine: AsyncEngine = create_async_engine(
        url=SETTINGS.ASYNC_OWNER_TEST_DB_URL, poolclass=NullPool
    )

    app_db_engine: AsyncEngine = create_async_engine(
        url=SETTINGS.ASYNC_APP_TEST_DB_URL, poolclass=NullPool
    )

    async with migration_db_engine.begin() as conn:
        await prepare_database(conn)

    yield app_db_engine

    async with migration_db_engine.begin() as conn:
        await clean_database(conn)

    await app_db_engine.dispose()
    await migration_db_engine.dispose()


@pytest_asyncio.fixture
async def session_maker(async_engine: AsyncEngine):
    async_connection: AsyncConnection = await async_engine.connect()
    async_transaction: AsyncTransaction = await async_connection.begin()

    session = async_sessionmaker(
        bind=async_connection,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    yield session

    await async_transaction.rollback()
    await async_connection.close()


@pytest_asyncio.fixture(scope="session")
async def _redis_client():
    try:
        redis_client: Redis = Redis.from_url(
            SETTINGS.TEST_REDIS_URL, decode_responses=True
        )
        yield redis_client
    finally:
        await redis_client.aclose()


@pytest_asyncio.fixture
async def test_redis_client(_redis_client):
    yield _redis_client


@pytest_asyncio.fixture(autouse=True)
async def flush_redis(test_redis_client: Redis):
    yield
    await test_redis_client.flushdb()


async def _no_rate_limit():
    return None


@pytest_asyncio.fixture
async def async_client(
    request: pytest.FixtureRequest,
    session_maker: async_sessionmaker[AsyncSession],
    test_redis_client: Redis,
):
    async def get_test_session():
        session = session_maker()
        yield session
        await session.aclose()

    app.dependency_overrides[get_session] = get_test_session
    app.dependency_overrides[get_redis_client] = lambda: test_redis_client

    # Rate limiting is disabled here, in the test harness, rather than by
    # anything a request can carry. Mark a test with
    # @pytest.mark.rate_limited to run it against the real limiters.
    if request.node.get_closest_marker("rate_limited") is None:
        app.dependency_overrides[read_limiter.dependency] = _no_rate_limit
        app.dependency_overrides[write_limiter.dependency] = _no_rate_limit

    async with (
        LifespanManager(app),
        AsyncClient(
            transport=ASGITransport(app), base_url="http://localhost/api/v1"
        ) as client,
    ):
        app.state.redis = test_redis_client

        yield client

    app.dependency_overrides.clear()


APP_ROLE = {
    "staff": {"id": uuid7(), "name": Role.STAFF},
    "admin": {"id": uuid7(), "name": Role.ADMIN},
    "payroll_officer": {"id": uuid7(), "name": Role.PAYROLL_OFFICER},
    "employee": {"id": uuid7(), "name": Role.EMPLOYEE},
}


async def _get_test_user():
    return UserInDB(
        id=uuid7(),
        role_id=APP_ROLE[Role.ADMIN]["id"],
        is_active=True,
        is_verified=True,
        email="user@example.com",
        hashed_password=await SECURITY.hash_password("test_user_password"),
    )


def _get_signup_payload():
    return {
        "email": "user@example.com",
        "password": "test_user_password",
        "organization_name": "test_org_name",
        "organization_country": "NGA",
    }


@pytest_asyncio.fixture(autouse=True)
async def seed_role(session_maker: async_sessionmaker):
    async with session_maker() as session:
        for v in APP_ROLE.values():
            session.add(DbRole(**v))
        await session.commit()


async def add_user_to_db(session_maker: async_sessionmaker, user: dict, org_id: UUID):
    async with session_maker() as session:
        user["organization_id"] = org_id

        await session.execute(
            insert(Organization)
            .values(id=org_id, name="test_org_name_", country="ESP")
            .on_conflict_do_nothing(index_elements=["id"])
        )

        session.add(User(**user))
        await session.commit()


async def get_user_from_db(session_maker: async_sessionmaker, key: str, value: str):
    filters = {"email": User.email, "google_email": User.google_email}
    async with session_maker() as session:
        res = await session.execute(select(User).where(filters[key] == value))
        return res.scalar()


@pytest_asyncio.fixture
async def create_user(async_client: AsyncClient):
    path: str = "app.api.services.auth.send_email.apply_async"

    with patch(path) as email_patch:
        res: Response = await async_client.post(
            "/auth/signup",
            json=_get_signup_payload(),
        )

    email_patch.assert_called_once()

    return res


@pytest_asyncio.fixture
async def login(session_maker: async_sessionmaker, async_client: AsyncClient):
    test_user = await _get_test_user()
    await add_user_to_db(session_maker, test_user.model_dump(), uuid7())

    login_payload: dict = {
        "email": "user@example.com",
        "password": "test_user_password",
    }

    res: Response = await async_client.post(
        "/auth/login",
        json=login_payload,
    )

    return res


async def add_user(
    org_id: UUID,
    session_maker: async_sessionmaker,
    *,
    role_key: str = "staff",
    email: str = "staff@example.com",
    is_active: bool = True,
    is_verified: bool = True,
) -> dict:
    user = (await _get_test_user()).model_dump()
    user.update(
        id=uuid7(),
        role_id=APP_ROLE[role_key]["id"],
        email=email,
        is_active=is_active,
        is_verified=is_verified,
    )
    await add_user_to_db(session_maker, user, org_id)
    return user


@pytest_asyncio.fixture
async def admin_user(
    session_maker: async_sessionmaker,
) -> AsyncGenerator[Awaitable[dict]]:
    async def _create(org_id: UUID):
        return await add_user(
            org_id,
            session_maker,
            role_key="admin",
            email=f"admin_{uuid4().hex[:8]}@example.com",
        )

    yield _create


@pytest_asyncio.fixture
async def employee_user(
    session_maker: async_sessionmaker,
) -> AsyncGenerator[Awaitable[dict]]:
    async def _create(org_id: UUID):
        return await add_user(
            org_id,
            session_maker,
            role_key="employee",
            email=f"employee_{uuid4().hex[:8]}@example.com",
        )

    yield _create


async def _login_user(async_client: AsyncClient, user: dict) -> dict[str, str]:
    res: Response = await async_client.post(
        "/auth/login",
        json={"email": user["email"], "password": "test_user_password"},
    )
    return {"Authorization": f"Bearer {res.json()['data']['access_token']}"}


async def add_employee_to_db(
    session_maker: async_sessionmaker,
    organization_id,
    **overrides,
) -> dict:
    employee = {
        "id": uuid7(),
        "first_name": "John",
        "last_name": "Doe",
        "email": f"employee_{uuid4().hex[:8]}@example.com",
        "organization_id": organization_id,
        "role_id": APP_ROLE["employee"]["id"],
        "is_active": True,
    }
    employee.update(overrides)

    async with session_maker() as session:
        session.add(Employee(**employee))
        await session.commit()

    return employee


async def add_employment_period_to_db(
    session_maker: async_sessionmaker,
    employee: dict,
    start_date,
    end_date=None,
    **overrides,
) -> dict:
    period = {
        "id": uuid7(),
        "employee_id": employee["id"],
        "organization_id": employee["organization_id"],
        "start_date": start_date,
        "end_date": end_date,
    }
    period.update(overrides)

    async with session_maker() as session:
        session.add(EmploymentPeriod(**period))
        await session.commit()

    return period


async def add_pay_to_db(
    session_maker: async_sessionmaker,
    employee: dict,
    created_by,
    effective_from,
    version: int = 1,
    **overrides,
) -> dict:
    pay = {
        "id": uuid7(),
        "employee_id": employee["id"],
        "organization_id": employee["organization_id"],
        "basic": "1000.00",
        "housing": "100.00",
        "transport": "50.00",
        "version": version,
        "effective_from": effective_from,
        "created_by": created_by,
    }
    pay.update(overrides)

    async with session_maker() as session:
        session.add(EmployeePay(**pay))
        await session.commit()

    return pay


def hash_invite_token(token: str) -> str:
    return SECURITY.hash_value_256(token, SETTINGS.INVITE_TOKEN_SECRET)


async def add_invite_to_db(
    session_maker: async_sessionmaker,
    employee: dict,
    created_by,
    token: str | None = None,
    status: InviteStatus = InviteStatus.ACTIVE,
    expires_at: datetime | None = None,
    **overrides,
) -> dict:
    token = token or secrets.token_urlsafe(32)

    invite = {
        "id": uuid7(),
        "employee_id": employee["id"],
        "organization_id": employee["organization_id"],
        "hashed_token": hash_invite_token(token),
        "created_by": created_by,
        "status": status,
        "expires_at": expires_at or (datetime.now(UTC) + timedelta(hours=1)),
    }
    invite.update(overrides)

    async with session_maker() as session:
        session.add(Invite(**invite))
        await session.commit()

    return {**invite, "token": token}
