from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from app.models.appointment import Appointment, AppointmentStatus
from app.models.records import (
    AIJobStatus,
    AISummary,
    CalendarEvent,
    CalendarSyncStatus,
    ClinicalNote,
    GoogleCalendarToken,
    MedicationReminder,
    MedicationStatus,
    Notification,
    NotificationStatus,
    Prescription,
    PrescriptionMedication,
    ReminderStatus,
    SymptomForm,
)
from app.services.ai_service import AIService
from app.services.booking import confirm_appointment
from app.services.calendar_service import CalendarService
from app.services.email_service import EmailService


def test_appointment_confirmation_succeeds_when_llm_fails(patient_a, doctor_user, db_session):
    """
    FAILURE INDEPENDENCE TEST 1:
    If the LLM provider fails / times out, the appointment confirmation must remain 100% CONFIRMED.
    """
    patient = patient_a.patient
    doctor = doctor_user.doctor

    now_utc = datetime.now(timezone.utc)
    app = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=now_utc + timedelta(days=2),
        end_time=now_utc + timedelta(days=2, minutes=30),
        status=AppointmentStatus.HELD,
        hold_expires_at=now_utc + timedelta(minutes=5),
    )
    db_session.add(app)
    db_session.commit()

    # Patient submitted symptoms before confirmation
    symptom_form = SymptomForm(
        appointment_id=app.id,
        symptoms="High fever and severe chills.",
    )
    db_session.add(symptom_form)
    db_session.commit()

    # Simulate catastrophic LLM outage
    with patch.object(AIService, "_call_llm_previsit", side_effect=Exception("LLM Gateway 503 Outage")):
        confirmed_res = confirm_appointment(
            db=db_session,
            appointment_id=app.id,
            patient_user=patient_a,
        )

        # 1. Appointment status is CONFIRMED
        assert confirmed_res.status == AppointmentStatus.CONFIRMED
        db_session.refresh(app)
        assert app.status == AppointmentStatus.CONFIRMED

        # 2. AI Service gracefully marks AI record as FAILED without breaking system
        summary = AIService.generate_previsit_summary(db_session, app.id)
        assert summary.status == AIJobStatus.FAILED


def test_appointment_confirmation_succeeds_when_email_fails(patient_a, doctor_user, db_session):
    """
    FAILURE INDEPENDENCE TEST 2:
    If SMTP / Email service fails, the appointment confirmation must remain 100% CONFIRMED.
    """
    patient = patient_a.patient
    doctor = doctor_user.doctor

    now_utc = datetime.now(timezone.utc)
    app = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=now_utc + timedelta(days=2),
        end_time=now_utc + timedelta(days=2, minutes=30),
        status=AppointmentStatus.HELD,
        hold_expires_at=now_utc + timedelta(minutes=5),
    )
    db_session.add(app)
    db_session.commit()

    with patch.object(EmailService, "_send_email", side_effect=Exception("SMTP Server Unreachable")):
        confirmed_res = confirm_appointment(
            db=db_session,
            appointment_id=app.id,
            patient_user=patient_a,
        )

        # 1. Appointment is CONFIRMED
        assert confirmed_res.status == AppointmentStatus.CONFIRMED
        db_session.refresh(app)
        assert app.status == AppointmentStatus.CONFIRMED

        # 2. Notification record is safely stored in database Outbox
        notif = db_session.query(Notification).filter(Notification.appointment_id == app.id).first()
        assert notif is not None
        assert notif.status == NotificationStatus.QUEUED


def test_appointment_confirmation_succeeds_when_calendar_fails(patient_a, doctor_user, db_session):
    """
    FAILURE INDEPENDENCE TEST 3:
    If Google Calendar API fails or token is revoked, appointment confirmation remains 100% CONFIRMED.
    """
    patient = patient_a.patient
    doctor = doctor_user.doctor

    now_utc = datetime.now(timezone.utc)
    app = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=now_utc + timedelta(days=2),
        end_time=now_utc + timedelta(days=2, minutes=30),
        status=AppointmentStatus.HELD,
        hold_expires_at=now_utc + timedelta(minutes=5),
    )
    db_session.add(app)
    db_session.commit()

    with patch.object(CalendarService, "_create_google_event", side_effect=Exception("Google Calendar API 500 Error")):
        confirmed_res = confirm_appointment(
            db=db_session,
            appointment_id=app.id,
            patient_user=patient_a,
        )

        # 1. Appointment is CONFIRMED
        assert confirmed_res.status == AppointmentStatus.CONFIRMED
        db_session.refresh(app)
        assert app.status == AppointmentStatus.CONFIRMED


def test_postvisit_ai_failure_preserves_clinical_notes_and_prescription(patient_a, doctor_user, db_session):
    """
    FAILURE INDEPENDENCE TEST 4:
    If Post-Visit AI fails, doctor's clinical notes, diagnosis, and prescription remain 100% intact.
    """
    patient = patient_a.patient
    doctor = doctor_user.doctor
    now_utc = datetime.now(timezone.utc)

    app = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=now_utc + timedelta(days=1),
        end_time=now_utc + timedelta(days=1, minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(app)
    db_session.flush()

    note = ClinicalNote(
        appointment_id=app.id,
        doctor_id=doctor.id,
        notes="Patient diagnosed with severe acute bronchitis.",
        diagnosis="Acute Bronchitis",
    )
    rx = Prescription(
        appointment_id=app.id,
        doctor_id=doctor.id,
        patient_id=patient.id,
    )
    db_session.add_all([note, rx])
    db_session.commit()

    with patch.object(AIService, "_call_llm_postvisit", side_effect=Exception("LLM Rate Limited 429")):
        summary = AIService.generate_postvisit_summary(db_session, app.id)

        assert summary.status == AIJobStatus.FAILED

        # Clinical note and diagnosis are 100% intact
        db_session.refresh(note)
        assert note.diagnosis == "Acute Bronchitis"
        assert note.notes == "Patient diagnosed with severe acute bronchitis."
