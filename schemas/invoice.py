
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.invoice import StatusEnum
from schemas import invoice_line


class InvoiceCreate(BaseModel):
    issue_date: date
    due_date: date
    customer_id: int
    invoice_lines: list[invoice_line.InvoiceLineCreate] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_dates(self):
        if self.due_date < self.issue_date:
            raise ValueError(
                "Due date must be on or after issue date"
            )
        return self


class InvoiceUpdate(BaseModel):
    update_invoice_lines: list[invoice_line.InvoiceLineUpdate] = Field(
        default_factory=list
    )
    create_invoice_lines: list[invoice_line.InvoiceLineCreate] = Field(
        default_factory=list
    )


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    customer_id: int
    invoice_number: str
    status: StatusEnum
    issue_date: date
    due_date: date
    subtotal: Decimal
    tax_total: Decimal
    total: Decimal
    email_sent_at: datetime | None
    paid_at: datetime | None
    invoice_lines: list[invoice_line.InvoiceLineResponse] = Field(
        default_factory=list
    )


class PaginatedInvoiceResponse(BaseModel):
    invoices: list[InvoiceResponse]
    total: int
    skip: int
    limit: int
    has_more: bool
