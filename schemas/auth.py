import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class CompanyRegister(BaseModel):
    company_name: str = Field(min_length=1, max_length=50)
    gstin: str | None = Field(default=None, max_length=15)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    invoice_prefix: str = Field(default="INV", min_length=1, max_length=7)

    admin_name: str = Field(min_length=1, max_length=100)
    email: str
    password: str = Field(min_length=12)

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, value: str | None) -> str | None:
        if not value:
            return value

        value = value.strip().upper()

        if not re.fullmatch(
            r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]",
            value,
        ):
            raise ValueError("Invalid GSTIN format")

        return value


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    gstin: str | None
    currency: str
    invoice_prefix: str
    invoice_next_number: int
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(max_length=120)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)
