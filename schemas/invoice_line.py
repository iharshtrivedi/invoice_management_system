
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from schemas.tax import TaxResponse


class InvoiceLineBase(BaseModel):
    description: str = Field(min_length=1, max_length=100)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class InvoiceLineCreate(InvoiceLineBase):
    tax_ids: list[int] = Field(default_factory=list)


class InvoiceLineUpdate(BaseModel):
    id: int
    description: str | None = Field(
        default=None, min_length=1, max_length=100
    )
    quantity: Decimal | None = Field(default=None, gt=0)
    unit_price: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    tax_ids: list[int] | None = None


class InvoiceLineResponse(InvoiceLineBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    line_total: Decimal
    taxes: list[TaxResponse] = Field(default_factory=list)
