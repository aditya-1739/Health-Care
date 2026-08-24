from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.records import (
    AIJobStatus,
    AISummaryType,
    MedicationStatus,
    PrescriptionStatus,
    ReminderStatus,
)


class SymptomFormCreate(BaseModel):
    symptoms: str = Field(..., min_length=3, max_length=5000, description="Patient-entered symptoms")
    chief_complaint: Optional[str] = Field(None, max_length=255)
    additional_notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("symptoms")
    def validate_symptoms_not_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Symptoms cannot be empty or whitespace only")
        return cleaned


class SymptomFormResponse(BaseModel):
    id: int
    appointment_id: int
    symptoms: str
    chief_complaint: Optional[str] = None
    additional_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AISummaryResponse(BaseModel):
    id: int
    appointment_id: int
    summary_type: AISummaryType
    urgency_level: Optional[str] = None
    chief_complaint: Optional[str] = None
    suggested_questions: Optional[List[str]] = None
    content: Optional[str] = None
    status: AIJobStatus
    retry_count: int
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClinicalNoteCreate(BaseModel):
    notes: str = Field(..., min_length=1, max_length=10000, description="Doctor's authoritative clinical notes")
    diagnosis: Optional[str] = Field(None, max_length=255, description="Authoritative doctor diagnosis")

    @field_validator("notes")
    def validate_notes(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Clinical notes cannot be empty")
        return cleaned


class ClinicalNoteResponse(BaseModel):
    id: int
    appointment_id: int
    doctor_id: int
    notes: str
    diagnosis: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PrescriptionMedicationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    dosage: str = Field(..., min_length=1, max_length=100)
    frequency: str = Field(..., min_length=1, max_length=100)
    start_date: date
    end_date: date
    instructions: Optional[str] = Field(None, max_length=1000)

    @field_validator("end_date")
    def validate_dates(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date cannot be earlier than start_date")
        return v


class PrescriptionMedicationResponse(BaseModel):
    id: int
    prescription_id: int
    name: str
    dosage: str
    frequency: str
    start_date: date
    end_date: date
    instructions: Optional[str] = None
    status: MedicationStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PrescriptionMedicationStatusUpdate(BaseModel):
    status: MedicationStatus


class PrescriptionCreate(BaseModel):
    general_instructions: Optional[str] = Field(None, max_length=2000)
    medications: List[PrescriptionMedicationCreate] = Field(..., min_length=1)


class PrescriptionResponse(BaseModel):
    id: int
    appointment_id: int
    doctor_id: int
    patient_id: int
    version: int
    status: PrescriptionStatus
    general_instructions: Optional[str] = None
    medications: List[PrescriptionMedicationResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MedicationReminderResponse(BaseModel):
    id: int
    prescription_medication_id: int
    patient_id: int
    medication_name: str
    dosage: str
    scheduled_at: datetime
    status: ReminderStatus
    sent_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
