from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.models.user import UserRole


def calculate_age(dob: Optional[date]) -> Optional[int]:
    if not dob:
        return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


class UserProfileResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole
    status: str
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    specialization: Optional[str] = None
    bio: Optional[str] = None
    slot_duration: Optional[int] = None
    active: Optional[bool] = None
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    profile_image_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    phone: Optional[str] = Field(None, max_length=50)
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = Field(None, max_length=255)
    emergency_contact_name: Optional[str] = Field(None, max_length=150)
    emergency_contact_phone: Optional[str] = Field(None, max_length=50)
    bio: Optional[str] = None
    specialization: Optional[str] = Field(None, max_length=100)

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: Optional[date]) -> Optional[date]:
        if v and v > date.today():
            raise ValueError("Date of birth cannot be in the future")
        if v and v < date(1900, 1, 1):
            raise ValueError("Date of birth is outside valid range")
        return v


class MedicalProfileResponse(BaseModel):
    id: Optional[int] = None
    patient_id: int
    blood_group: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    current_medications: Optional[str] = None
    past_surgeries: Optional[str] = None
    family_history: Optional[str] = None
    medical_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class MedicalProfileUpdate(BaseModel):
    blood_group: Optional[str] = Field(None, max_length=10)
    height_cm: Optional[float] = Field(None, ge=30, le=300)
    weight_kg: Optional[float] = Field(None, ge=1, le=500)
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    current_medications: Optional[str] = None
    past_surgeries: Optional[str] = None
    family_history: Optional[str] = None
    medical_notes: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)

    @field_validator("confirm_password")
    def passwords_match(cls, v, values):
        if "new_password" in values.data and v != values.data["new_password"]:
            raise ValueError("New password and confirm password do not match")
        return v


class AppointmentHistoryItem(BaseModel):
    id: int
    doctor_id: int
    doctor_name: str
    doctor_specialization: str
    patient_id: int
    patient_name: str
    start_time: datetime
    end_time: datetime
    status: str
    cancellation_reason: Optional[str] = None
    decline_remarks: Optional[str] = None
    chief_complaint: Optional[str] = None
    has_prescription: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppointmentHistoryResponse(BaseModel):
    upcoming: List[AppointmentHistoryItem]
    past: List[AppointmentHistoryItem]
    cancelled: List[AppointmentHistoryItem]
    total: int


class AdminUserDetailResponse(BaseModel):
    user: UserProfileResponse
    patient: Optional[Dict[str, Any]] = None
    medical_profile: Optional[MedicalProfileResponse] = None
    doctor: Optional[Dict[str, Any]] = None
    appointments_count: int = 0
    recent_appointments: List[AppointmentHistoryItem] = []
