from datetime import date
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.user import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)


class RegisterPatientRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    phone: Optional[str] = Field(None, max_length=50)
    date_of_birth: Optional[date] = None


class UserProfileResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole
    status: str
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    profile_image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfileResponse


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None
    exp: Optional[int] = None
