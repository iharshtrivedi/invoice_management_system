from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    email: EmailStr = Field(max_length=120)
    tax_id: str = Field(max_length=50)
    billing_address: str = Field(min_length=1, max_length=200)


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    company_id: int
    email: EmailStr
    tax_id: str
    billing_address: str

class PaginatedCustomersResponse(BaseModel):
    customers: list[CustomerResponse]
    total: int
    skip: int
    limit: int
    has_more: bool


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    email: EmailStr | None = Field(default=None, max_length=120)
    tax_id: str | None = Field(default=None, max_length=50)
    billing_address: str | None = Field(default=None, min_length=1, max_length=200)
