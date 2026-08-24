from datetime import date, time, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.user import LeaveStatus
from app.schemas.appointment import AppointmentResponse


class WorkingHoursResponse(BaseModel):
    id: int
    day_of_week: int
    start_time: time
    end_time: time

    model_config = ConfigDict(from_attributes=True)


class WorkingHoursCreate(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: time
    end_time: time


class DoctorLeaveResponse(BaseModel):
    id: int
    doctor_id: int
    start_date: date
    end_date: date
    reason: Optional[str] = None
    status: LeaveStatus = LeaveStatus.PENDING
    requested_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by_user_id: Optional[int] = None
    admin_remarks: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DoctorLeaveCreate(BaseModel):
    start_date: date
    end_date: date
    reason: str = Field(..., min_length=1, max_length=500, description="Reason for leave request")


class DoctorLeaveWithConflictsResponse(BaseModel):
    leave: DoctorLeaveResponse
    affected_appointments: List[AppointmentResponse] = []


class DoctorUpdateAdmin(BaseModel):
    specialization: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = None
    slot_duration: Optional[int] = Field(None, ge=10, le=120)
    active: Optional[bool] = None


class DoctorStatusUpdate(BaseModel):
    active: bool


class DoctorPublicResponse(BaseModel):
    id: int
    user_id: int
    name: str
    email: EmailStr
    specialization: str
    bio: Optional[str] = None
    slot_duration: int
    active: bool
    working_hours: List[WorkingHoursResponse] = []

    model_config = ConfigDict(from_attributes=True)
