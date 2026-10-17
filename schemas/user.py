from pydantic import BaseModel, ConfigDict, EmailStr, Field

from models import user as user_model


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    email: EmailStr = Field(max_length=120)
    password: str = Field(min_length=8)
    role: user_model.UserRole = user_model.UserRole.STAFF


class UserResponsePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    company_id: int


class UserResponse(UserResponsePublic):
    email: EmailStr


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    email: EmailStr | None = Field(default=None, max_length=120)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)
