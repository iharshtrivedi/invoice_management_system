from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    status,
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import company as company_model
from models import user as user_model
from schemas import auth
from services.auth_service import (
    create_access_token,
    generate_access_token,
    hash_password,
    hash_reset_token,
    verify_password,
    verify_user_role,
)
from services.database import get_db
from utils import email_utils

router = APIRouter()


@router.post(
    '/register-company',
    response_model=auth.CompanyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_company(company: auth.CompanyRegister, db: Annotated[AsyncSession, Depends(get_db)]):
    # Check for unique company name
    result = await db.execute(
        select(company_model.Company).where(
            func.lower(company_model.Company.name) == company.company_name.lower(),
        ),
    )
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company with the same name already exists",
        )

    # Check for unique GSTIN
    if company.gstin:
        result = await db.execute(
            select(company_model.Company).where(func.lower(company_model.Company.gstin) == company.gstin.lower()),
        )
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Company with the same GSTIN number already exists.",
            )

    result = await db.execute(
        select(user_model.User).where(
            func.lower(user_model.User.email) == company.email.lower(),
        )
    )
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with same email already exists."
        )

    new_company = company_model.Company(
        name=company.company_name,
        gstin=company.gstin,
        currency=company.currency,
        invoice_prefix=company.invoice_prefix,
    )
    db.add(new_company)
    await db.commit()
    await db.refresh(new_company)

    new_user = user_model.User(
        name=company.admin_name,
        email=company.email.lower(),
        hashed_password=hash_password(company.password),
        company_id=new_company.id,
        role='admin',
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_company


@router.delete(
    '/deregister-company/{company_id}',
    status_code=status.HTTP_204_NO_CONTENT
)
async def deregister_company(
    company_id: int,
    current_user: Annotated[user_model.User, Depends(verify_user_role('admin'))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(company_model.Company).where(
            (company_model.Company.id == company_id)
            & (current_user.company_id == company_id)
        )
    )
    company = result.scalars().first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )
    await db.delete(company)
    await db.commit()


@router.post(
    '/token',
    response_model=auth.Token,
)
async def user_login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    results = await db.execute(
        select(user_model.User).where(
            func.lower(user_model.User.email) == form_data.username.lower(),
        )
    )
    user = results.scalars().first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Incorrect email or password',
            headers={'WWW-Authenticate': 'Bearer'},
        )

    access_token_expires = timedelta(minutes=settings.access_token_expires_minutes)
    access_token = create_access_token(
        data={'sub': str(user.id)},
        expires_delta=access_token_expires,
    )
    return auth.Token(access_token=access_token, token_type='bearer')


@router.post(
    '/forgot-password',
    status_code=status.HTTP_202_ACCEPTED,
)
async def forgot_password(
    request_data: auth.ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(user_model.User).where(
            func.lower(user_model.User.email) == request_data.email.lower()
        )
    )
    user = result.scalars().first()
    if user:
        await db.execute(
            sql_delete(user_model.PasswordResetToken).where(
                user_model.PasswordResetToken.user_id == user.id
            )
        )
        token = generate_access_token()
        token_hash = hash_reset_token(token)
        expires_at = datetime.now(UTC) + timedelta(
            minutes=settings.reset_token_expire_minutes,
        )

        reset_token = user_model.PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        db.add(reset_token)
        await db.commit()

        background_tasks.add_task(
            email_utils.send_password_reset_email,
            to_email=user.email,
            username=user.name,
            token=token,
        )

    return {
        "message": "If an account exists with this email, you will receive password reset instructions.",
    }


@router.post('/reset-password', status_code=status.HTTP_200_OK)
async def reset_password(
    request_data: auth.ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    token_hash = hash_reset_token(request_data.token)

    result = await db.execute(
        select(user_model.PasswordResetToken).where(
            user_model.PasswordResetToken.token_hash == token_hash
        )
    )
    reset_token = result.scalars().first()

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid or expired reset token',
        )

    if reset_token.expires_at < datetime.now(UTC):
        if reset_token.expires_at < datetime.now(UTC):
            await db.delete(reset_token)
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid or expired reset token',
        )

    user_result = await db.execute(
        select(user_model.User).where(user_model.User.id == reset_token.user_id),
    )
    user = user_result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user.hashed_password = hash_password(request_data.new_password)

    await db.execute(
        sql_delete(user_model.PasswordResetToken).where(
            user_model.PasswordResetToken.user_id == user.id,
        ),
    )
    await db.commit()
    return {
        'message': 'Password reset successfully. You can now log in with your new password.',
    }
