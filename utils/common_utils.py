from collections.abc import Sequence

from fastapi import (
    HTTPException,
    status,
)
from pydantic import EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.interfaces import ORMOption


async def ensure_email_is_unique(
    db: AsyncSession,
    target_model,
    email: EmailStr,
    company_id: int,
):
    stmt = (
        select(target_model).where(
            (func.lower(target_model.email) == email.lower())
            & (target_model.company_id == company_id)
        )
    )
    is_registered = await db.scalar(stmt)
    if is_registered:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'{target_model.__name__} email is already registered.',
        )


async def get_target_object(
    db: AsyncSession,
    target_model,
    target_id: int,
    company_id: int,
    target_model_options: Sequence[ORMOption] | None = None,
):
    stmt = select(target_model).where(
        (target_model.id == target_id)
        & (company_id == target_model.company_id)
    )
    if target_model_options is not None:
        stmt = stmt.options(*target_model_options)
    target_object = await db.scalar(stmt)
    if not target_object:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{target_model.__name__} not found",
        )
    return target_object
