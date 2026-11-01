from typing import Literal

from pydantic import BaseModel, Field


class PaymentWebhookPayload(BaseModel):
    event_id: str = Field(min_length=1, max_length=128)
    invoice_id: int = Field(gt=0)
    payment_status: Literal['paid']
