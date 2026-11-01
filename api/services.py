from typing import Annotated

import base64

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import invoice as invoice_model
from models import invoice_line as invoice_line_model
from schemas import invoice
from services.auth_service import CurrentUser
from services.database import get_db
from utils.common_utils import get_target_object
from utils.pdf_utils import generate_invoice_pdf
from tasks.email_tasks import send_email_task

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

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


async def send_invoice_email(
    to_email: str,
    customer_name: str,
    invoice: invoice_model.Invoice,
    pdf_bytes: bytes,
):
    template = templates.env.get_template(
        "email/send_invoice.html"
    )

    html_content = template.render(
        company_name=invoice.company.name,
        customer_name=customer_name,
        invoice_number=invoice.invoice_number,
        issue_date=invoice.issue_date.strftime("%d %b %Y"),
        due_date=invoice.due_date.strftime("%d %b %Y"),
        currency=invoice.company.currency,
        total=f"{invoice.total:,.2f}",
        status=invoice.status.value,
    )

    plain_text = f"""Hi {customer_name},

Please find your invoice details below.

Invoice Number: {invoice.invoice_number}
Invoice Date: {invoice.issue_date:%d %b %Y}
Due Date: {invoice.due_date:%d %b %Y}
Amount: {invoice.company.currency} {invoice.total:,.2f}
Status: {invoice.status.value.upper()}

The invoice PDF is attached to this email.

Thank you for your business!

Best regards,
The Invoice Management System Team
"""

    task = send_email_task.delay(
        to_email=to_email,
        subject=f"Invoice {invoice.invoice_number}",
        plain_text=plain_text,
        html_content=html_content,
        attachments=[
            {
                "filename": f"invoice_{invoice.invoice_number}.pdf",
                # Celery is configured for JSON; binary attachments must be encoded.
                "content": base64.b64encode(pdf_bytes).decode("ascii"),
            }
        ],
    )

    return task.id


@router.post('/send-invoice/{invoice_id}', status_code=status.HTTP_200_OK)
async def send_invoice(
    invoice_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
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

    task_id = await send_invoice_email(
        to_email=customer_email,
        customer_name=customer_name,
        invoice=inv,
        pdf_bytes=pdf_bytes,
    )

    inv.email_status = invoice_model.EmailStatusEnum.QUEUED
    inv.email_task_id = task_id
    inv.email_sent_at = None
    await db.commit()
    await db.refresh(inv)

    return {
        "message": "An email will be sent to the customer's mail address shortly.",
        "invoice_number": inv.invoice_number,
        "task_id": task_id,
    }
