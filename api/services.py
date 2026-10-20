from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import invoice as invoice_model
from models import invoice_line as invoice_line_model
from models import tax as tax_model
from schemas import invoice
from services.auth_service import CurrentUser
from services.database import get_db
from utils.pdf_utils import generate_invoice_pdf
from utils.email_utils import send_invoice_email
from fastapi import BackgroundTasks

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
        .options(
            selectinload(invoice_model.Invoice.invoice_lines)
            .selectinload(invoice_line_model.InvoiceLine.taxes)
        )
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
    return inv


@router.patch(
    '/reset-invoice/{invoice_id}',
    response_model=invoice.InvoiceResponse,
)
async def reset_invoice(
    invoice_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(invoice_model.Invoice)
        .options(
            selectinload(invoice_model.Invoice.invoice_lines)
            .selectinload(invoice_line_model.InvoiceLine.taxes)
        )
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

    inv.status = invoice_model.StatusEnum.DRAFT
    await db.commit()
    await db.refresh(inv)
    return inv


@router.patch(
    '/cancel-invoice/{invoice_id}',
    response_model=invoice.InvoiceResponse,
)
async def cancel_invoice(
    invoice_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(invoice_model.Invoice)
        .options(
            selectinload(invoice_model.Invoice.invoice_lines)
            .selectinload(invoice_line_model.InvoiceLine.taxes)
        )
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

    inv.status = invoice_model.StatusEnum.CANCELLED
    await db.commit()
    await db.refresh(inv)
    return inv


@router.get("/invoices/{invoice_id}/pdf")
async def generate_pdf(
    invoice_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(invoice_model.Invoice)
        .options(
            selectinload(invoice_model.Invoice.company),
            selectinload(invoice_model.Invoice.invoice_lines)
            .selectinload(invoice_line_model.InvoiceLine.taxes)
        )
        .where(
            (invoice_model.Invoice.id == invoice_id)
            & (invoice_model.Invoice.company_id == current_user.company_id)
        )
    )
    inv = result.scalars().first()

    if inv is None:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found",
        )

    pdf_bytes = generate_invoice_pdf(inv)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="invoice_{inv.invoice_number}.pdf"'
            )
        },
    )


@router.post('/send-invoice/{invoice_id}', status_code=status.HTTP_200_OK)
async def send_invoice(
    invoice_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
):
    result = await db.execute(
        select(invoice_model.Invoice)
        .where(
            invoice_model.Invoice.id == invoice_id,
            invoice_model.Invoice.company_id == current_user.company_id,
        )
        .options(
            selectinload(invoice_model.Invoice.company),
            selectinload(invoice_model.Invoice.invoice_lines)
            .selectinload(invoice_line_model.InvoiceLine.taxes),
            selectinload(invoice_model.Invoice.customer),
        )
    )

    inv = result.scalar_one_or_none()

    if inv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )

    # Replace with your actual customer relationship and email field.
    customer_email = inv.customer.email
    customer_name = inv.customer.name

    if not customer_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer email is not configured",
        )

    pdf_bytes = generate_invoice_pdf(inv)

    background_tasks.add_task(
        send_invoice_email,
        to_email=customer_email,
        customer_name=customer_name,
        invoice=inv,
        pdf_bytes=pdf_bytes,
    )

    inv.status = invoice_model.StatusEnum.DRAFT
    await db.commit()
    await db.refresh(inv)

    return {
        "message": "An email will be sent to the customer's mail address shortly.",
        "invoice_number": inv.invoice_number,
    }
