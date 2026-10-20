from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import tax as tax_model
from schemas import tax
from services.auth_service import CurrentUser
from services.database import get_db

router = APIRouter()


@router.post(
    '',
    response_model=tax.TaxResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tax(
    tax_request_data: tax.TaxCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(tax_model.Tax).where(
            (tax_model.Tax.name == tax_request_data.name)
            & (tax_model.Tax.company_id == current_user.company_id)
        )
    )
    tax = result.scalars().first()
    if tax:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Tax with same name already exists.'
        )

    new_tax = tax_model.Tax(
        name=tax_request_data.name,
        amount=tax_request_data.amount,
        tax_type=tax_request_data.tax_type,
        company_id=current_user.company_id,
        created_by=current_user.id,
        updated_by=current_user.id,
    )
    db.add(new_tax)
    await db.commit()
    await db.refresh(new_tax)
    return new_tax


@router.get(
    '',
    response_model=tax.PaginatedTaxResponse,
)
async def get_taxes(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=0, le=100)] = settings.items_per_page
):
    tax_count_result = await db.execute(
            select(func.count())
            .where(tax_model.Tax.company_id == current_user.company_id)
        )
    total = tax_count_result.scalar() or 0

    result = await db.execute(
        select(tax_model.Tax)
        .where(tax_model.Tax.company_id == current_user.company_id)
        .order_by(tax_model.Tax.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    taxes = result.scalars().all()
    has_more = skip + len(taxes) < total

    return tax.PaginatedTaxResponse(
        taxes=[tax.TaxResponse.model_validate(t) for t in taxes],
        total=total,
        skip=skip,
        limit=limit,
        has_more=has_more,
    )


@router.get(
    '/{tax_id}',
    response_model=tax.TaxResponse,
)
async def get_tax(
    tax_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(tax_model.Tax).where(
            (tax_model.Tax.id == tax_id)
            & (tax_model.Tax.company_id == current_user.company_id)
        )
    )
    tax = result.scalars().first()
    if tax:
        return tax
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail='Tax not found',
    )


@router.patch(
    '/{tax_id}',
    response_model=tax.TaxResponse,
)
async def update_tax(
    tax_id: int,
    tax_update: tax.TaxUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(tax_model.Tax).where(
            (tax_model.Tax.id == tax_id)
            & (tax_model.Tax.company_id == current_user.company_id)
        )
    )
    tax = result.scalars().first()
    if not tax:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Tax not found',
        )

    if tax_update.name is not None and tax_update.name != tax.name:
        result = await db.execute(
            select(tax_model.Tax).where(
                (tax_model.Tax.name == tax_update.name)
                & (tax_model.Tax.company_id == current_user.company_id)
            )
        )
        existing_tax_name = result.scalars().first()
        if existing_tax_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Tax with same name already exists.'
            ) 

    if tax_update.name is not None:
        tax.name = tax_update.name
    if tax_update.amount is not None:
        tax.amount = tax_update.amount
    if tax_update.tax_type is not None:
        tax.tax_type = tax_update.tax_type
    tax.updated_by = current_user.id

    await db.commit()
    await db.refresh(tax)
    return tax


@router.delete(
    '/{tax_id}',
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_tax(
    tax_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(tax_model.Tax).where(
            (tax_model.Tax.id == tax_id)
            & (tax_model.Tax.company_id == current_user.company_id)
        )
    )
    tax = result.scalars().first()
    if not tax:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Tax not found',
        )
    await db.delete(tax)
    await db.commit()
