from celery import Celery

from config import settings

celery_app = Celery(
    "invoice_management",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["tasks.email_tasks", "tasks.invoice_tasks"],
)


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    beat_schedule={
        "reconcile-invoice-email-statuses": {
            "task": "tasks.reconcile_invoice_email_statuses",
            "schedule": 60.0,
        },
    },
)
