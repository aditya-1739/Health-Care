import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class UserRole(str, enum.Enum):
    PATIENT = "PATIENT"
    DOCTOR = "DOCTOR"
    ADMIN = "ADMIN"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.PATIENT)
    status = Column(String(50), nullable=False, default="active")
    phone = Column(String(50), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    patient = relationship("Patient", back_populates="user", uselist=False, cascade="all, delete-orphan")
    doctor = relationship("Doctor", back_populates="user", uselist=False, cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")
    notifications = relationship("Notification", back_populates="user")


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    phone = Column(String(50), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True)
    address = Column(String(255), nullable=True)
    emergency_contact_name = Column(String(150), nullable=True)
    emergency_contact_phone = Column(String(50), nullable=True)
    preferences = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="patient")
    medical_profile = relationship(
        "PatientMedicalProfile",
        back_populates="patient",
        uselist=False,
        cascade="all, delete-orphan",
    )
    appointments = relationship("Appointment", back_populates="patient")
    medication_reminders = relationship("MedicationReminder", back_populates="patient")


class PatientMedicalProfile(Base):
    __tablename__ = "patient_medical_profiles"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    blood_group = Column(String(10), nullable=True)
    height_cm = Column(Float, nullable=True)
    weight_kg = Column(Float, nullable=True)
    allergies = Column(Text, nullable=True)
    chronic_conditions = Column(Text, nullable=True)
    current_medications = Column(Text, nullable=True)
    past_surgeries = Column(Text, nullable=True)
    family_history = Column(Text, nullable=True)
    medical_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    patient = relationship("Patient", back_populates="medical_profile")


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    specialization = Column(String(100), nullable=False, index=True)
    bio = Column(Text, nullable=True)
    slot_duration = Column(Integer, nullable=False, default=30)  # minutes
    active = Column(Boolean, nullable=False, default=True)
    phone = Column(String(50), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="doctor")
    working_hours = relationship(
        "DoctorWorkingHours",
        back_populates="doctor",
        cascade="all, delete-orphan",
    )
    leaves = relationship(
        "DoctorLeave",
        back_populates="doctor",
        cascade="all, delete-orphan",
    )
    appointments = relationship("Appointment", back_populates="doctor")
    clinical_notes = relationship("ClinicalNote", back_populates="doctor")
    prescriptions = relationship("Prescription", back_populates="doctor")


class DoctorWorkingHours(Base):
    __tablename__ = "doctor_working_hours"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_of_week = Column(Integer, nullable=False)  # 0=Monday ... 6=Sunday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    # Relationship
    doctor = relationship("Doctor", back_populates="working_hours")


class LeaveStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    CANCELLED = "CANCELLED"


class DoctorLeave(Base):
    __tablename__ = "doctor_leaves"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(
        Integer,
        ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(
        Enum(LeaveStatus, name="leavestatus"),
        nullable=False,
        default=LeaveStatus.APPROVED,
        server_default="APPROVED",
        index=True,
    )
    requested_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    admin_remarks = Column(Text, nullable=True)

    # Relationships
    doctor = relationship("Doctor", back_populates="leaves")
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])
