import asyncio
from datetime import UTC, datetime

from celery.result import AsyncResult
from sqlalchemy import select

from models.invoice import EmailStatusEnum, Invoice, StatusEnum
from services.celery_app import celery_app
from services.database import AsyncSessionLocal


@celery_app.task(name="tasks.reconcile_invoice_email_statuses")
def reconcile_invoice_email_statuses() -> dict[str, int]:
    """Sync completed Celery email tasks back to invoice state."""
    return asyncio.run(_reconcile_invoice_email_statuses())


async def _reconcile_invoice_email_statuses() -> dict[str, int]:
    updated_sent = 0
    updated_failed = 0

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Invoice).where(
                Invoice.email_status == EmailStatusEnum.QUEUED,
                Invoice.email_task_id.is_not(None),
            )
        )

        for invoice in result.scalars():
            task_result = AsyncResult(invoice.email_task_id, app=celery_app)
            if task_result.successful():
                invoice.email_status = EmailStatusEnum.SENT
                # The schema uses a timezone-naive UTC timestamp column.
                invoice.email_sent_at = datetime.now(UTC).replace(tzinfo=None)
                # Do not overwrite a later paid or cancelled state.
                if invoice.status == StatusEnum.CONFIRMED:
                    invoice.status = StatusEnum.SENT
                updated_sent += 1
            elif task_result.failed():
                invoice.email_status = EmailStatusEnum.FAILED
                updated_failed += 1

        if updated_sent or updated_failed:
            await db.commit()

    return {"sent": updated_sent, "failed": updated_failed}
