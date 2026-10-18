from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import customer as customer_model
from schemas import customer
from services.auth_service import CurrentUser
from services.database import get_db

router = APIRouter()


@router.post(
    '',
    response_model=customer.CustomerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_customer(
    customer: customer.CustomerCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(customer_model.Customer).where(
            (func.lower(customer_model.Customer.email) == customer.email.lower())
            & (customer_model.Customer.company_id == current_user.company_id)
        )
    )
    customer_registered = result.scalars().first()
    if customer_registered:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Customer email is already registered.',
        )
    new_customer = customer_model.Customer(
        name=customer.name,
        email=customer.email,
        tax_id=customer.tax_id,
        billing_address=customer.billing_address,
        company_id=current_user.company_id,
        created_by=current_user.id,
    )
    db.add(new_customer)
    await db.commit()
    await db.refresh(new_customer)
    return new_customer


@router.get(
    '',
    response_model=customer.PaginatedCustomersResponse,
)
async def get_customers(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=0, le=100)] = settings.items_per_page
):
    customer_count_result = await db.execute(
        select(func.count())
        .where(customer_model.Customer.company_id == current_user.company_id)
    )
    total = customer_count_result.scalar() or 0

    result = await db.execute(
        select(customer_model.Customer)
        .where(customer_model.Customer.company_id == current_user.company_id)
        .order_by(customer_model.Customer.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    customers = result.scalars().all()
    has_more = skip + len(customers) < total

    return customer.PaginatedCustomersResponse(
        customers=[customer.CustomerResponse.model_validate(c) for c in customers],
        total=total,
        skip=skip,
        limit=limit,
        has_more=has_more,
    )


@router.get(
    '/{customer_id}',
    response_model=customer.CustomerResponse,
)
async def get_customer(
    customer_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(customer_model.Customer).where(
            (customer_model.Customer.id == customer_id)
            & (customer_model.Customer.company_id == current_user.company_id)
        )
    )
    customer = result.scalars().first()
    if customer:
        return customer
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail='Customer not found',
    )


@router.patch(
    '/{customer_id}',
    response_model=customer.CustomerResponse,
)
async def update_customer(
    customer_id: int,
    customer_update: customer.CustomerUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(customer_model.Customer).where(
            (customer_model.Customer.id == customer_id)
            & (customer_model.Customer.company_id == current_user.company_id)
        )
    )
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Customer not found',
        )

    if (
        customer_update.email is not None
        and customer_update.email.lower() != customer.email.lower()
    ):
        result = await db.execute(
            select(customer_model.Customer).where(
                (func.lower(customer_model.Customer.email) == customer_update.email.lower())
                & (customer_model.Customer.company_id == current_user.company_id)
            )
        )
        existing_email = result.scalars().first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Email already registered',
            )

    if customer_update.name is not None:
        customer.name = customer_update.name
    if customer_update.email is not None:
        customer.email = customer_update.email.lower()
    if customer_update.tax_id is not None:
        customer.tax_id = customer_update.tax_id
    if customer_update.billing_address is not None:
        customer.billing_address = customer_update.billing_address
    customer.updated_by = current_user.id

    await db.commit()
    await db.refresh(customer)
    return customer


@router.delete(
    '/{customer_id}',
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_customer(
    customer_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(customer_model.Customer).where(
            (customer_model.Customer.id == customer_id)
            & (customer_model.Customer.company_id == current_user.company_id)
        )
    )
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Customer not found',
        )
    await db.delete(customer)
    await db.commit()
