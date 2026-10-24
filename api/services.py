from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import invoice as invoice_model
from models import invoice_line as invoice_line_model
from schemas import invoice
from services.auth_service import CurrentUser
from services.database import get_db
from utils.common_utils import get_target_object
from utils.email_utils import send_invoice_email
from utils.pdf_utils import generate_invoice_pdf

router = APIRouter()


async def update_inv_status(
    db: AsyncSession,
    company_id: int,
    invoice_id: int,
    target_inv_status: invoice_model.StatusEnum,
    required_inv_statuses: list[invoice_model.StatusEnum] | None = None,
    error_msg: str | None = None,
):
    options = (
        selectinload(invoice_model.Invoice.invoice_lines)
        .selectinload(invoice_line_model.InvoiceLine.taxes),
    )
    inv = await get_target_object(
        db=db,
        target_model=invoice_model.Invoice,
        target_id=invoice_id,
        company_id=company_id,
        target_model_options=options,
    )
    if required_inv_statuses is not None and inv.status not in required_inv_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    inv.status = target_inv_status
    await db.commit()
    await db.refresh(inv)
    return inv


@router.patch(
    '/confirm-invoice/{invoice_id}',
    response_model=invoice.InvoiceResponse,
)
async def confirm_invoice(
    invoice_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    return await update_inv_status(
        db=db,
        company_id=current_user.company_id,
        invoice_id=invoice_id,
        required_inv_statuses=[invoice_model.StatusEnum.DRAFT],
        target_inv_status=invoice_model.StatusEnum.CONFIRMED,
        error_msg='Only draft invoices can be confirmed',
    )


@router.patch(
    '/reset-invoice/{invoice_id}',
    response_model=invoice.InvoiceResponse,
)
async def reset_invoice(
    invoice_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    return await update_inv_status(
        db=db,
        company_id=current_user.company_id,
        invoice_id=invoice_id,
        target_inv_status=invoice_model.StatusEnum.DRAFT,
    )


@router.patch(
    '/cancel-invoice/{invoice_id}',
    response_model=invoice.InvoiceResponse,
)
async def cancel_invoice(
    invoice_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    return await update_inv_status(
        db=db,
        company_id=current_user.company_id,
        invoice_id=invoice_id,
        target_inv_status=invoice_model.StatusEnum.CANCELLED,
    )


@router.get("/invoices/{invoice_id}/pdf")
async def generate_pdf(
    invoice_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    options = (
        selectinload(invoice_model.Invoice.invoice_lines)
        .selectinload(invoice_line_model.InvoiceLine.taxes),
    )
    inv = await get_target_object(
        db=db,
        target_model=invoice_model.Invoice,
        target_id=invoice_id,
        company_id=current_user.company_id,
        target_model_options=options,
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
    options = (
        selectinload(invoice_model.Invoice.company),
        selectinload(invoice_model.Invoice.invoice_lines)
        .selectinload(invoice_line_model.InvoiceLine.taxes),
        selectinload(invoice_model.Invoice.customer),
    )
    inv = await get_target_object(
        db=db,
        target_model=invoice_model.Invoice,
        target_id=invoice_id,
        company_id=current_user.company_id,
        target_model_options=options,
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
