import asyncio
import os
import tempfile
from collections import defaultdict
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / "invoice_management_system_tests.sqlite3"
os.environ.update(
    {
        "DATABASE_URL": f"sqlite+aiosqlite:///{TEST_DATABASE_PATH.as_posix()}",
        "SECRET_KEY": "test-secret-key-that-is-at-least-32-bytes",
        "CELERY_BROKER_URL": "redis://unused/0",
        "CELERY_RESULT_BACKEND": "redis://unused/1",
        "REDIS_URL": "redis://unused/2",
        "PAYMENT_WEBHOOK_SECRET": "test-payment-webhook-secret",
    }
)

from main import app
from services.database import Base, engine


class FakeRedis:
    """Small Redis eval replacement used by the rate-limit dependency."""

    def __init__(self):
        self.counts: defaultdict[str, int] = defaultdict(int)

    async def eval(self, _script: str, _key_count: int, key: str, window: int):
        self.counts[key] += 1
        return self.counts[key], window

    async def aclose(self) -> None:
        pass


async def _reset_database() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr("main.Redis.from_url", lambda *args, **kwargs: fake_redis)
    asyncio.run(_reset_database())
    with TestClient(app) as test_client:
        yield test_client
    asyncio.run(_reset_database())


@pytest.fixture
def registered_user(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/register-company",
        json={
            "company_name": "Acme Ltd",
            "admin_name": "Admin User",
            "email": "admin@acme.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert response.status_code == 201, response.text

    response = client.post(
        "/api/auth/token",
        data={"username": "admin@acme.com", "password": "correct-horse-battery-staple"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
