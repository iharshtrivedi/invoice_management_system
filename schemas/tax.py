
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from models.tax import TaxTypeEnum


class TaxBase(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    amount: Decimal = Field(ge=0)
    tax_type: TaxTypeEnum = TaxTypeEnum.PERCENT


class TaxCreate(TaxBase):
    pass


class TaxUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    amount: Decimal | None = Field(default=None, ge=0)
    tax_type: TaxTypeEnum | None = None


class TaxResponse(TaxBase):
    model_config = ConfigDict(from_attributes=True)

    id: int

class PaginatedTaxResponse(BaseModel):
    taxes: list[TaxResponse]
    total: int
    skip: int
    limit: int
    has_more: bool
