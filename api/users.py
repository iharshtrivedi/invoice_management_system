from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Delete as sql_delete
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
from utils.common_utils import ensure_email_is_unique, get_target_object

router = APIRouter()


@router.get('/me', response_model=user.UserResponse)
async def get_current_user(current_user: CurrentUser):
    return current_user


@router.get("/{user_id}", response_model=user.UserResponsePublic)
async def get_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    return await get_target_object(
        db=db,
        target_model=user_model.User,
        target_id=user_id,
        company_id=current_user.company_id,
    )


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
    await ensure_email_is_unique(
        db=db,
        target_model=user_model.User,
        email=user.email,
        company_id=current_user.company_id,
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

    user = await get_target_object(
        db=db,
        target_model=user_model.User,
        target_id=user_id,
        company_id=current_user.company_id,
    )

    if (
        user_update.email is not None
        and user_update.email.lower() != user.email.lower()
    ):
        await ensure_email_is_unique(
            db=db,
            target_model=user_model.User,
            email=user.email,
            company_id=current_user.company_id,
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
    user = await get_target_object(
        db=db,
        target_model=user_model.User,
        target_id=user_id,
        company_id=current_user.company_id,
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

    await db.execute(
        sql_delete(user_model.PasswordResetToken).where(
            user_model.PasswordResetToken.user_id == current_user.id,
        ),
    )
    await db.commit()

    return {'message': 'Password changed successfully'}
