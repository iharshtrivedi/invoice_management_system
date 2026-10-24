from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from models import company as company_model
from models import customer as customer_model
from models import invoice as invoice_model
from models import invoice_line as invoice_line_model
from models import tax as tax_model
from schemas import invoice
from services.auth_service import CurrentUser
from services.database import get_db
from utils.common_utils import get_target_object

router = APIRouter()


@router.post(
    '',
    response_model=invoice.InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invoice(
    invoice_request_data: invoice.InvoiceCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    customer = await get_target_object(
        db=db,
        target_model=customer_model.Customer,
        target_id=invoice_request_data.customer_id,
        company_id=current_user.company_id,
    )
    
    comp_result = await db.execute(
        select(company_model.Company).where(
            company_model.Company.id == current_user.company_id
        )
    )
    company = comp_result.scalar_one()

    invoice_number = (
        f"{company.invoice_prefix}{company.invoice_next_number:05d}"
    )
    company.invoice_next_number += 1

    tax_ids = [
        tax_id
        for line in invoice_request_data.invoice_lines
        for tax_id in line.tax_ids
    ]
    taxes: Sequence[tax_model.Tax] = []
    if tax_ids:
        result = await db.execute(
            select(tax_model.Tax)
            .where(
                (tax_model.Tax.id.in_(tax_ids))
                & (tax_model.Tax.company_id == current_user.company_id)
            )
        )
        taxes = result.scalars().all()
        if len(taxes) != len(set(tax_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more taxes are invalid or do not belong to your company.",
            )
    taxes_by_id = {tax.id: tax for tax in taxes}
    missing_tax_ids = tax_ids - taxes_by_id.keys()
    
    if missing_tax_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown tax IDs: {sorted(missing_tax_ids)}",
        )

    invoice_subtotal = Decimal('0.00')
    invoice_tax_total = Decimal('0.00')
    invoice_lines: list[invoice_line_model.InvoiceLine] = []
    for line in invoice_request_data.invoice_lines:
        line_subtotal = line.quantity * line.unit_price
        line_tax_total = Decimal('0.00')
        line_taxes = [taxes_by_id[tax_id] for tax_id in line.tax_ids]
        for tax in line_taxes:
            if tax.tax_type == 'percent':
                line_tax_total += ((line_subtotal * tax.amount) / Decimal(100))
            else:
                line_tax_total += tax.amount
        line_tax_total = line_tax_total.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        line_total = line_subtotal + line_tax_total
        invoice_subtotal += line_subtotal
        invoice_tax_total += line_tax_total

        invoice_line = invoice_line_model.InvoiceLine(
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price,
            line_subtotal=line_subtotal,
            line_tax_total=line_tax_total,
            line_total=line_total,
            taxes=line_taxes,
            created_by=current_user.id,
            updated_by=current_user.id,
        )
        invoice_lines.append(invoice_line)

    invoice_subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    invoice_tax_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    new_invoice = invoice_model.Invoice(
        invoice_number=invoice_number,
        invoice_lines=invoice_lines,
        issue_date=invoice_request_data.issue_date,
        due_date=invoice_request_data.due_date,
        subtotal=invoice_subtotal,
        tax_total=invoice_tax_total,
        total=(invoice_subtotal + invoice_tax_total),
        company_id=current_user.company_id,
        customer_id=customer.id,
        created_by=current_user.id,
        updated_by=current_user.id,
    )

    db.add(new_invoice)
    await db.commit()
    await db.refresh(new_invoice)

    new_invoice_query = await db.execute(
        select(invoice_model.Invoice)
        .options(
            selectinload(invoice_model.Invoice.invoice_lines)
            .selectinload(invoice_line_model.InvoiceLine.taxes)
        )
        .where(invoice_model.Invoice.id == new_invoice.id)
    )
    new_invoice = new_invoice_query.scalar_one()

    return new_invoice


@router.get(
    '',
    response_model=invoice.PaginatedInvoiceResponse,
)
async def get_invoices(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=0, le=100)] = settings.items_per_page
):
    inv_count_res = await db.execute(
        select(func.count())
        .where(invoice_model.Invoice.company_id == current_user.company_id)
    )
    total = inv_count_res.scalar() or 0

    result = await db.execute(
        select(invoice_model.Invoice)
        .options(
            selectinload(invoice_model.Invoice.invoice_lines)
            .selectinload(invoice_line_model.InvoiceLine.taxes)
        )
        .where(invoice_model.Invoice.company_id == current_user.company_id)
        .order_by(invoice_model.Invoice.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    invoices = result.scalars().all()
    has_more = skip + len(invoices) < total

    return invoice.PaginatedInvoiceResponse(
        invoices=[invoice.InvoiceResponse.model_validate(inv) for inv in invoices],
        total=total,
        skip=skip,
        limit=limit,
        has_more=has_more,
    )


@router.get(
    '/{invoice_id}',
    response_model=invoice.InvoiceResponse,
)
async def get_invoice(
    invoice_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    options = (
        selectinload(invoice_model.Invoice.invoice_lines)
        .selectinload(invoice_line_model.InvoiceLine.taxes),
    )
    return await get_target_object(
        db=db,
        target_model=invoice_model.Invoice,
        target_id=invoice_id,
        company_id=current_user.company_id,
        target_model_options=options,
    )


# @router.patch(
#     '/{invoice_id}',
#     response_model=invoice.InvoiceResponse,
# )
# async def update_invoice(
#     invoice_id: int,
#     invoice_update: invoice.InvoiceUpdate,
#     db: Annotated[AsyncSession, Depends(get_db)],
#     current_user: CurrentUser,
# ):
#     inv_result = await db.execute(
#         select(invoice_model.Invoice)
#         .where(
#             (invoice_model.Invoice.id == invoice_id)
#             & (invoice_model.Invoice.company_id == current_user.company_id)
#         )
#     )
#     invoice = inv_result.scalars().first()
#     if not invoice:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail='Invoice not found'
#         )

#     if invoice.status != 'draft':
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail='Only draft invoices can be updated'
#         )

#     invoice_lines_by_id = {line.id: line for line in invoice_update.update_invoice_lines}
#     for line_update in invoice_update.update_invoice_lines:
#         if line_update.id not in invoice_lines_by_id:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail=(
#                     f"Invoice line {line_update.id} "
#                     "not found on this invoice"
#                 ),
#             )

#     tax_ids = [
#         tax_id
#         for line in (invoice_update.update_invoice_lines + invoice_update.create_invoice_lines)
#         if line.tax_ids is not None
#         for tax_id in line.tax_ids
#     ]
#     taxes: Sequence[tax_model.Tax] = []
#     if tax_ids:
#         tax_result = await db.execute(
#             select(tax_model.Tax)
#             .where(
#                 (tax_model.Tax.id.in_(tax_ids))
#                 & (tax_model.Tax.company_id == current_user.company_id)
#             )
#         )
#         taxes = tax_result.scalars().all()

#         if len(taxes) != len(set(tax_ids)):
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="One or more taxes are invalid or do not belong to your company.",
#             )

#     taxes_by_id = {tax.id: tax for tax in taxes}    
#     missing_tax_ids = tax_ids - taxes_by_id.keys()

#     if missing_tax_ids:
#         raise HTTPException(
#             status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
#             detail=f"Unknown tax IDs: {sorted(missing_tax_ids)}",
#         )

#     for line_update in invoice_update.update_invoice_lines:
#         line = invoice_lines_by_id[line_update.id]

#         changes = line_update.model_dump(
#             exclude_unset=True,
#             exclude={"id", "tax_ids"},
#         )

#         for field, value in changes.items():
#             setattr(line, field, value)

#         if line_update.tax_ids is not None:
#             line.taxes = [
#                 taxes_by_id[tax_id]
#                 for tax_id in line_update.tax_ids
#             ]

#     # Create new lines.
#     for line_create in invoice_update.create_invoice_lines:
#         new_line = invoice_model.InvoiceLine(
#             description=line_create.description,
#             quantity=line_create.quantity,
#             unit_price=line_create.unit_price,
#             taxes=[
#                 taxes_by_id[tax_id]
#                 for tax_id in line_create.tax_ids
#             ],
#         )

#         invoice.invoice_lines.append(new_line)


@router.delete(
    '/{invoice_id}',
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_invoice(
    invoice_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    invoice = await get_target_object(
        db=db,
        target_model=invoice_model.Invoice,
        target_id=invoice_id,
        company_id=current_user.company_id,
    )
    await db.delete(invoice)
    await db.commit()
