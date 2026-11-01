import asyncio

from services.celery_app import celery_app
from services.email_service import send_email


@celery_app.task(
    name="tasks.send_email",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_email_task(
    to_email: str,
    subject: str,
    plain_text: str,
    html_content: str | None = None,
    attachments: list[dict] | None = None,
):
    asyncio.run(
        send_email(
            to_email=to_email,
            subject=subject,
            plain_text=plain_text,
            html_content=html_content,
            attachments=attachments,
        )
    )

    return {
        "status": "sent",
        "to_email": to_email,
    }
