from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.user import UserRole


class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: UserRole
    status: str = "active"


class UserCreateAdmin(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: UserRole = Field(..., description="Role must be DOCTOR or ADMIN")
    # If role == DOCTOR:
    specialization: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = None
    slot_duration: Optional[int] = Field(30, ge=10, le=120)


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole
    status: str
    created_at: datetime
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    profile_image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
