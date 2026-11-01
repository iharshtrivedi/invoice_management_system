import hashlib
import hmac
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import invoice as invoice_model
from models import webhook as webhook_model
from schemas.webhook import PaymentWebhookPayload
from services.database import get_db

router = APIRouter()


def _signature_is_valid(payload: bytes, signature: str | None) -> bool:
    secret = settings.payment_webhook_secret.get_secret_value()
    if not secret or not signature:
        return False
    supplied_signature = signature.removeprefix('sha256=')
    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(supplied_signature, expected_signature)


@router.post('/payment', status_code=status.HTTP_200_OK)
async def receive_payment_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_payment_signature: Annotated[str | None, Header()] = None,
):
    raw_payload = await request.body()
    if not _signature_is_valid(raw_payload, x_payment_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid webhook signature',
        )

    try:
        payment = PaymentWebhookPayload.model_validate_json(raw_payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Invalid webhook payload',
        ) from exc

    existing_event = await db.scalar(
        select(webhook_model.WebhookEvent).where(
            webhook_model.WebhookEvent.event_id == payment.event_id,
        )
    )
    if existing_event:
        return {'status': 'duplicate', 'event_id': payment.event_id}

    invoice = await db.scalar(
        select(invoice_model.Invoice).where(
            invoice_model.Invoice.id == payment.invoice_id,
        )
    )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Invoice not found',
        )
    if invoice.status == invoice_model.StatusEnum.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Cancelled invoices cannot be paid',
        )

    db.add(
        webhook_model.WebhookEvent(
            event_id=payment.event_id,
            invoice_id=invoice.id,
            payload=payment.model_dump(mode='json'),
        )
    )
    if invoice.status != invoice_model.StatusEnum.PAID:
        invoice.status = invoice_model.StatusEnum.PAID
        invoice.paid_at = datetime.now(UTC).replace(tzinfo=None)

    try:
        await db.commit()
    except IntegrityError:
        # Another worker committed the same event after our initial lookup.
        await db.rollback()
        return {'status': 'duplicate', 'event_id': payment.event_id}

    return {'status': 'processed', 'event_id': payment.event_id}
