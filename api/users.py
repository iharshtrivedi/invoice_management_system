from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import user as user_model
from schemas import user
from services.auth_service import (
    CurrentUser,
    hash_password,
    verify_password,
    verify_user_role,
)
from services.database import get_db

router = APIRouter()


@router.get('/me', response_model=user.UserResponse)
async def get_current_user(current_user: CurrentUser):
    return current_user


@router.get("/{user_id}", response_model=user.UserResponsePublic)
async def get_user(user_id: int, current_user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(user_model.User).where(
            (user_model.User.id == user_id)
            & (user_model.User.company_id == current_user.company_id)
        )
    )
    user = result.scalars().first()
    if user:
        return user
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.post(
    '',
    response_model=user.UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    user: user.UserCreate,
    current_user: Annotated[user_model.User, Depends(verify_user_role('admin'))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(user_model.User).where(
            (func.lower(user_model.User.email) == user.email.lower())
            & (user_model.User.company_id == current_user.company_id)
        )
    )
    existing_email = result.scalars().first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Email already registered!',
        )

    new_user = user_model.User(
        name=user.name,
        email=user.email.lower(),
        hashed_password=hash_password(user.password),
        company_id=current_user.company_id,
        role=user.role,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.patch(
    '/{user_id}',
    response_model=user.UserResponse,
)
async def update_user(
    user_id: int,
    user_update: user.UserUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user",
        )

    result = await db.execute(select(user_model.User).where(
            (user_model.User.id == user_id)
            & (user_model.User.company_id == current_user.company_id)
        )
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if (
        user_update.email is not None
        and user_update.email.lower() != user.email.lower()
    ):
        result = await db.execute(
            select(user_model.User).where(
                (func.lower(user_model.User.email) == user_update.email.lower())
                & (user_model.User.company_id == current_user.company_id)
            ),
        )
        existing_email = result.scalars().first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    if user_update.name is not None:
        user.name = user_update.name
    if user_update.email is not None:
        user.email = user_update.email.lower()

    await db.commit()
    await db.refresh(user)
    return user


@router.delete('/{user_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if user_id != current_user.id:
        verify_user_role('admin')
    result = await db.execute(select(user_model.User).where(
            (user_model.User.id == user_id)
            & (user_model.User.company_id == current_user.company_id)
        )
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    await db.delete(user)
    await db.commit()


@router.post(
    'me/change-password',
    status_code=status.HTTP_200_OK,
)
async def change_password(
    password_data: user.ChangePasswordRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Current Password is incorrect',
        )
    current_user.hashed_password = hash_password(password_data.new_password)
    return {'message': 'Password changed successfully'}
