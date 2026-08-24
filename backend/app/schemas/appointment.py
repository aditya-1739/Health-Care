from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.appointment import AppointmentStatus


class AppointmentHoldRequest(BaseModel):
    doctor_id: int
    start_time: datetime = Field(..., description="UTC start time of the slot")
    idempotency_key: Optional[str] = None


class AppointmentHoldResponse(BaseModel):
    appointment_id: int
    doctor_id: int
    patient_id: int
    start_time: datetime
    end_time: datetime
    status: AppointmentStatus
    hold_expires_at: datetime
    remaining_seconds: int

    model_config = ConfigDict(from_attributes=True)


class AppointmentConfirmRequest(BaseModel):
    idempotency_key: Optional[str] = None


class AppointmentCancelRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500, description="Reason for cancellation")


class AppointmentDeclineRequest(BaseModel):
    remarks: str = Field(..., min_length=1, max_length=1000, description="Doctor remarks for declining the appointment")


class AppointmentRescheduleRequest(BaseModel):
    new_start_time: datetime = Field(..., description="Target new UTC start time")
    idempotency_key: Optional[str] = None


class AppointmentResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    start_time: datetime
    end_time: datetime
    status: AppointmentStatus
    hold_expires_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    cancelled_by_user_id: Optional[int] = None
    cancelled_at: Optional[datetime] = None
    rescheduled_from_id: Optional[int] = None
    doctor_name: Optional[str] = None
    doctor_specialization: Optional[str] = None
    patient_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SlotResponse(BaseModel):
    start_time: datetime
    end_time: datetime
    available: bool

    model_config = ConfigDict(from_attributes=True)


class DoctorAvailabilityResponse(BaseModel):
    doctor_id: int
    doctor_name: str
    date: date
    slot_duration: int
    total_slots: int
    available_slots_count: int
    slots: List[SlotResponse]

    model_config = ConfigDict(from_attributes=True)


class AlternativeSlot(BaseModel):
    start_time: datetime
    end_time: datetime
    doctor_id: int
    doctor_name: str
    score: float
    reason: str


class AlternativeSlotsResponse(BaseModel):
    appointment_id: int
    original_start_time: datetime
    suggestions: List[AlternativeSlot]
