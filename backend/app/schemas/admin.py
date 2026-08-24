from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.user import LeaveStatus, UserRole
from app.schemas.appointment import AppointmentResponse


class AdminDashboardStats(BaseModel):
    total_users: int
    total_patients: int
    total_doctors: int
    active_doctors: int
    total_appointments: int


class AdminPatientResponse(BaseModel):
    id: int
    user_id: int
    name: str
    email: str
    phone: Optional[str] = None
    status: str
    created_at: datetime
    appointments_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class AdminLeaveRequestResponse(BaseModel):
    id: int
    doctor_id: int
    doctor_name: str
    doctor_specialization: str
    doctor_email: str
    start_date: date
    end_date: date
    reason: Optional[str] = None
    status: LeaveStatus
    requested_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by_user_id: Optional[int] = None
    admin_remarks: Optional[str] = None
    affected_appointments_count: int = 0
    affected_appointments: List[AppointmentResponse] = []

    model_config = ConfigDict(from_attributes=True)


class AdminLeaveReviewRequest(BaseModel):
    remarks: Optional[str] = Field(None, max_length=1000, description="Remarks from administrator")


class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    resource: str
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
