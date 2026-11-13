from collections.abc import Generator
from typing import Any

from redis import Redis
from redis.backoff import ExponentialBackoff
from redis.connection import ConnectionPool
from redis.exceptions import ConnectionError, TimeoutError
from redis.retry import Retry
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.session import sync_session

SETTINGS = get_settings()

redis_pool = ConnectionPool.from_url(
    SETTINGS.REDIS_URL,
    decode_responses=True,
    max_connections=50,
    retry=Retry(ExponentialBackoff(cap=1.0, base=0.1), retries=5),
    retry_on_error=(TimeoutError, ConnectionError),
    retry_on_timeout=True,
)


def get_db_session() -> Generator[Session, Any]:
    with sync_session() as session:
        yield session


def get_redis_client() -> Generator[Redis, Any]:
    with Redis(connection_pool=redis_pool) as redis:
        yield redis
