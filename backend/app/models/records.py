import enum
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class AISummaryType(str, enum.Enum):
    PRE_VISIT = "PRE_VISIT"
    POST_VISIT = "POST_VISIT"


class AIJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PrescriptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    MODIFIED = "MODIFIED"
    DISCONTINUED = "DISCONTINUED"
    CANCELLED = "CANCELLED"


class MedicationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DISCONTINUED = "DISCONTINUED"
    COMPLETED = "COMPLETED"


class ReminderStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NotificationStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"


class CalendarSyncStatus(str, enum.Enum):
    PENDING = "PENDING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"
    NOT_CONNECTED = "NOT_CONNECTED"


class CalendarConnectionStatus(str, enum.Enum):
    NOT_CONNECTED = "NOT_CONNECTED"
    CONNECTED = "CONNECTED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    REVOKED = "REVOKED"


class SymptomForm(Base):
    __tablename__ = "symptom_forms"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    symptoms = Column(Text, nullable=False)
    chief_complaint = Column(String(255), nullable=True)
    additional_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    appointment = relationship("Appointment", back_populates="symptom_form")


class AISummary(Base):
    __tablename__ = "ai_summaries"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary_type = Column(Enum(AISummaryType), nullable=False)
    urgency_level = Column(String(50), nullable=True)  # Low / Medium / High
    chief_complaint = Column(Text, nullable=True)
    suggested_questions = Column(JSON, nullable=True)  # List[str] of 3 questions
    content = Column(Text, nullable=True)  # Post-visit plain language explanation
    status = Column(Enum(AIJobStatus), default=AIJobStatus.PENDING, nullable=False, index=True)
    retry_count = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
    idempotency_key = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    appointment = relationship("Appointment", back_populates="ai_summaries")


class ClinicalNote(Base):
    __tablename__ = "clinical_notes"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notes = Column(Text, nullable=False)
    diagnosis = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    appointment = relationship("Appointment", back_populates="clinical_note")
    doctor = relationship("Doctor", back_populates="clinical_notes")


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version = Column(Integer, default=1, nullable=False)
    status = Column(Enum(PrescriptionStatus), default=PrescriptionStatus.ACTIVE, nullable=False, index=True)
    general_instructions = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    appointment = relationship("Appointment", back_populates="prescription")
    doctor = relationship("Doctor", back_populates="prescriptions")
    patient = relationship("Patient")
    medications = relationship(
        "PrescriptionMedication",
        back_populates="prescription",
        cascade="all, delete-orphan",
        order_by="PrescriptionMedication.id.asc()",
    )


class PrescriptionMedication(Base):
    __tablename__ = "prescription_medications"

    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(
        Integer,
        ForeignKey("prescriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(150), nullable=False)
    dosage = Column(String(100), nullable=False)
    frequency = Column(String(100), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    instructions = Column(Text, nullable=True)
    status = Column(Enum(MedicationStatus), default=MedicationStatus.ACTIVE, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    prescription = relationship("Prescription", back_populates="medications")
    reminders = relationship(
        "MedicationReminder",
        back_populates="medication",
        cascade="all, delete-orphan",
    )


class MedicationReminder(Base):
    __tablename__ = "medication_reminders"

    id = Column(Integer, primary_key=True, index=True)
    prescription_medication_id = Column(
        Integer,
        ForeignKey("prescription_medications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    medication_name = Column(String(150), nullable=False)
    dosage = Column(String(100), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)
    status = Column(Enum(ReminderStatus), default=ReminderStatus.PENDING, nullable=False, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    idempotency_key = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    medication = relationship("PrescriptionMedication", back_populates="reminders")
    patient = relationship("Patient", back_populates="medication_reminders")

    __table_args__ = (
        UniqueConstraint("prescription_medication_id", "scheduled_at", name="uq_med_reminder_sched"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    type = Column(String(50), default="EMAIL", nullable=False)
    event_type = Column(String(100), nullable=False, index=True)
    recipient_email = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    body_html = Column(Text, nullable=False)
    status = Column(Enum(NotificationStatus), default=NotificationStatus.QUEUED, nullable=False, index=True)
    retry_count = Column(Integer, default=0, nullable=False)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    idempotency_key = Column(String(255), nullable=True, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="notifications")
    appointment = relationship("Appointment")


class GoogleCalendarToken(Base):
    __tablename__ = "google_calendar_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    encrypted_access_token = Column(Text, nullable=True)
    encrypted_refresh_token = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    connection_status = Column(
        Enum(CalendarConnectionStatus),
        default=CalendarConnectionStatus.NOT_CONNECTED,
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(
        Integer,
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(50), default="google", nullable=False)
    google_event_id = Column(String(255), nullable=True)
    sync_status = Column(Enum(CalendarSyncStatus), default=CalendarSyncStatus.PENDING, nullable=False, index=True)
    retry_count = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
    idempotency_key = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    appointment = relationship("Appointment", back_populates="calendar_events")
    user = relationship("User")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = Column(String(100), nullable=False, index=True)
    resource = Column(String(100), nullable=False)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="audit_logs")


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), nullable=False, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action = Column(String(100), nullable=False)
    request_hash = Column(String(64), nullable=False)
    response_code = Column(Integer, nullable=False)
    response_body = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("user_id", "action", "key", name="uq_user_action_idempotency_key"),
    )
