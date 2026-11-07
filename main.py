from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api import auth, customers, invoices, services, taxes, users, webhooks
from config import settings
from services.database import engine, get_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    yield
    # Shutdown
    await _app.state.redis.aclose()
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(customers.router, prefix="/api/customers", tags=["customers"])
app.include_router(taxes.router, prefix="/api/taxes", tags=['taxes'])
app.include_router(invoices.router, prefix="/api/invoices", tags=['invoices'])
app.include_router(services.router, prefix="/api/services", tags=['services'])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=['webhooks'])


@app.get("/", include_in_schema=False)
async def home():
    """Redirect visitors to the interactive API documentation."""
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health_check(db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc
    return {"status": "healthy"}
