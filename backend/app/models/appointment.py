import enum
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class AppointmentStatus(str, enum.Enum):
    HELD = "HELD"
    CONFIRMED = "CONFIRMED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"
    EXPIRED = "EXPIRED"


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(
        Enum(AppointmentStatus),
        nullable=False,
        default=AppointmentStatus.HELD,
        index=True,
    )
    hold_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Cancellation audit
    cancellation_reason = Column(Text, nullable=True)
    cancelled_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    # Rescheduling tracking
    rescheduled_from_id = Column(
        Integer,
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Idempotency tracking
    idempotency_key = Column(String(255), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    cancelled_by = relationship("User", foreign_keys=[cancelled_by_user_id])
    rescheduled_from = relationship(
        "Appointment",
        remote_side=[id],
        foreign_keys=[rescheduled_from_id],
    )

    symptom_form = relationship(
        "SymptomForm",
        back_populates="appointment",
        uselist=False,
        cascade="all, delete-orphan",
    )
    ai_summaries = relationship(
        "AISummary",
        back_populates="appointment",
        cascade="all, delete-orphan",
    )
    clinical_note = relationship(
        "ClinicalNote",
        back_populates="appointment",
        uselist=False,
        cascade="all, delete-orphan",
    )
    prescription = relationship(
        "Prescription",
        back_populates="appointment",
        uselist=False,
        cascade="all, delete-orphan",
    )
    calendar_events = relationship(
        "CalendarEvent",
        back_populates="appointment",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_appointments_doctor_start_status",
            "doctor_id",
            "start_time",
            "status",
        ),
    )
