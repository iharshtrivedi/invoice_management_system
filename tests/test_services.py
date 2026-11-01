import asyncio
from datetime import timedelta
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from config import settings
from services.auth_service import (
    create_access_token,
    hash_password,
    hash_reset_token,
    verify_access_token,
    verify_password,
)
from services.rate_limiter import rate_limit


def test_password_and_token_helpers_round_trip():
    password_hash = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", password_hash)
    assert not verify_password("wrong-password", password_hash)
    assert hash_reset_token("token") == hash_reset_token("token")

    token = create_access_token({"sub": "42"}, timedelta(minutes=1))
    assert verify_access_token(token) == "42"
    assert verify_access_token("not-a-token") is None


def test_expired_jwt_is_rejected():
    token = jwt.encode(
        {"sub": "42", "exp": 0},
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )
    assert verify_access_token(token) is None


def test_limiter_returns_503_when_redis_is_unavailable():
    class BrokenRedis:
        async def eval(self, *args):
            from redis.exceptions import ConnectionError

            raise ConnectionError("unavailable")

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "app": SimpleNamespace(state=SimpleNamespace(redis=BrokenRedis())),
        }
    )
    async def enforce_limit() -> None:
        await rate_limit(limit=1, window_seconds=60, scope="test")(request)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(enforce_limit())
    assert exc_info.value.status_code == 503
