from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import invoice as invoice_model
from models import invoice_line as invoice_line_model
from models import tax as tax_model
from schemas import invoice
from services.auth_service import CurrentUser
from services.database import get_db

router = APIRouter()


@router.patch(
    '/confirm-invoice/{invoice_id}',
    response_model=invoice.InvoiceResponse,
)
async def confirm_invoice(
    invoice_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(invoice_model.Invoice)
        .where(
            (invoice_model.Invoice.id == invoice_id)
            & (invoice_model.Invoice.company_id == current_user.company_id)
        )
    )
    inv = result.scalars().first()
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Invoice not found'
        )

    if inv.status == 'draft':
        inv.status = invoice_model.StatusEnum.CONFIRMED
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Only draft invoices can be confirmed'
        )  

    await db.commit()
    await db.refresh(inv)
    return invoice
