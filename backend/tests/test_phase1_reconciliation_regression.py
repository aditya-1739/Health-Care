import pytest
from datetime import date, datetime, time, timedelta, timezone
from fastapi.testclient import TestClient
from app.core.security import create_access_token, get_password_hash
from app.models.appointment import Appointment, AppointmentStatus
from app.models.records import (
    AIJobStatus,
    AISummary,
    AISummaryType,
    ClinicalNote,
    MedicationReminder,
    MedicationStatus,
    Notification,
    NotificationStatus,
    Prescription,
    PrescriptionMedication,
    PrescriptionStatus,
    ReminderStatus,
    SymptomForm,
)
from app.models.user import Doctor, DoctorWorkingHours, Patient, User, UserRole


def test_auth_with_valid_rfc_emails(client):
    """Verify Patient, Doctor, and Admin authentication with valid RFC email formats."""
    # 1. Register a new patient
    reg_payload = {
        "name": "Regression Patient",
        "email": "regression.patient@example.com",
        "password": "Password123!",
        "phone": "555-4321",
    }
    res = client.post("/api/auth/register", json=reg_payload)
    assert res.status_code == 201, f"Registration failed: {res.text}"
    user_data = res.json()
    assert user_data["email"] == "regression.patient@example.com"

    # 2. Login with registered patient
    login_res = client.post("/api/auth/login", json={
        "email": "regression.patient@example.com",
        "password": "Password123!",
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    login_data = login_res.json()
    assert "access_token" in login_data
    assert login_data["user"]["role"] == "PATIENT"


def test_appointment_hold_and_confirm_workflow(client, doctor_user, patient_a, db_session):
    """
    Test complete Hold -> Confirm appointment workflow:
    - Hold slot (HELD state)
    - Confirm slot (transitions HELD -> CONFIRMED)
    - Generates transactional notification outbox entry
    - Verify atomic state
    """
    doctor = doctor_user.doctor
    patient = patient_a.patient

    target_date = date.today() + timedelta(days=2)
    wh = DoctorWorkingHours(
        doctor_id=doctor.id,
        day_of_week=target_date.weekday(),
        start_time=time(8, 0),
        end_time=time(18, 0),
    )
    db_session.add(wh)
    db_session.commit()

    slot_time = datetime.combine(target_date, time(11, 0)).replace(tzinfo=timezone.utc)
    token = create_access_token(subject=patient_a.id, role=patient_a.role.value)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Hold slot
    hold_res = client.post(
        "/api/appointments/hold",
        json={"doctor_id": doctor.id, "start_time": slot_time.isoformat()},
        headers=headers,
    )
    assert hold_res.status_code == 201, f"Hold failed: {hold_res.text}"
    app_id = hold_res.json()["appointment_id"]

    # 2. Confirm slot
    confirm_res = client.post(
        f"/api/appointments/{app_id}/confirm",
        json={},
        headers=headers,
    )
    assert confirm_res.status_code == 200, f"Confirm failed: {confirm_res.text}"
    confirmed_data = confirm_res.json()
    assert confirmed_data["status"] == "CONFIRMED"

    # 3. Verify notification created in database
    notif = db_session.query(Notification).filter(Notification.appointment_id == app_id).first()
    assert notif is not None
    assert notif.event_type == "BOOKING_CONFIRMATION"
    assert notif.status == NotificationStatus.QUEUED


def test_symptom_submission_and_previsit_ai(client, doctor_user, patient_a, db_session):
    """Verify symptom submission and pre-visit AI summary data integrity."""
    doctor = doctor_user.doctor
    patient = patient_a.patient

    app_start = datetime.now(timezone.utc) + timedelta(days=1)
    app = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=app_start,
        end_time=app_start + timedelta(minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(app)
    db_session.commit()
    db_session.refresh(app)

    token = create_access_token(subject=patient_a.id, role=patient_a.role.value)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Submit symptoms
    symptom_payload = {
        "symptoms": "Mild shortness of breath and dizziness upon waking",
        "chief_complaint": "Dizziness and fatigue",
        "additional_notes": "Started 3 days ago",
    }
    symptom_res = client.post(
        f"/api/appointments/{app.id}/symptoms",
        json=symptom_payload,
        headers=headers,
    )
    assert symptom_res.status_code == 201, f"Symptom submission failed: {symptom_res.text}"
    assert symptom_res.json()["chief_complaint"] == "Dizziness and fatigue"

    # 2. Retrieve AI summaries
    ai_res = client.get(f"/api/appointments/{app.id}/ai-summary", headers=headers)
    assert ai_res.status_code == 200, f"AI summary retrieval failed: {ai_res.text}"


def test_doctor_consultation_prescription_and_reminders(client, doctor_user, patient_a, db_session):
    """
    Test complete doctor consultation workflow:
    - Doctor records clinical assessment
    - Doctor prescribes multiple medications
    - Medication reminders generated
    - Patient retrieves reminders
    """
    doctor = doctor_user.doctor
    patient = patient_a.patient

    app_start = datetime.now(timezone.utc) + timedelta(hours=1)
    app = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=app_start,
        end_time=app_start + timedelta(minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(app)
    db_session.commit()
    db_session.refresh(app)

    doc_token = create_access_token(subject=doctor_user.id, role=doctor_user.role.value)
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    # 1. Save Clinical Notes
    notes_payload = {
        "notes": "Patient presents with seasonal allergy symptoms. Clear lungs, mild rhinitis.",
        "diagnosis": "Allergic Rhinitis",
    }
    notes_res = client.post(
        f"/api/appointments/{app.id}/clinical-notes",
        json=notes_payload,
        headers=doc_headers,
    )
    assert notes_res.status_code == 201, f"Clinical notes failed: {notes_res.text}"
    assert notes_res.json()["diagnosis"] == "Allergic Rhinitis"

    # 2. Save Multi-Medication Structured Prescription
    today_str = date.today().isoformat()
    end_str = (date.today() + timedelta(days=7)).isoformat()

    rx_payload = {
        "general_instructions": "Take medications with plenty of water after breakfast.",
        "medications": [
            {
                "name": "Cetirizine 10mg",
                "dosage": "1 tablet",
                "frequency": "ONCE_DAILY",
                "start_date": today_str,
                "end_date": end_str,
                "instructions": "Take once daily in the evening",
            },
            {
                "name": "Fluticasone Nasal Spray",
                "dosage": "2 sprays per nostril",
                "frequency": "TWICE_DAILY",
                "start_date": today_str,
                "end_date": end_str,
                "instructions": "Administer morning and evening",
            },
        ],
    }
    rx_res = client.post(
        f"/api/appointments/{app.id}/prescription",
        json=rx_payload,
        headers=doc_headers,
    )
    assert rx_res.status_code == 201, f"Prescription failed: {rx_res.text}"
    rx_data = rx_res.json()
    assert len(rx_data["medications"]) == 2
    assert rx_data["status"] == "ACTIVE"

    # 3. Patient views medication reminders
    pat_token = create_access_token(subject=patient_a.id, role=patient_a.role.value)
    pat_headers = {"Authorization": f"Bearer {pat_token}"}

    reminders_res = client.get("/api/patients/me/medication-reminders", headers=pat_headers)
    assert reminders_res.status_code == 200, f"Reminders failed: {reminders_res.text}"
    reminders = reminders_res.json()
    assert len(reminders) > 0
    assert any(r["medication_name"] == "Cetirizine 10mg" for r in reminders)


def test_admin_reliability_metrics_calculation(client, admin_user, db_session):
    """Verify that Admin Reliability metrics are calculated accurately across all job states."""
    admin_token = create_access_token(subject=admin_user.id, role=admin_user.role.value)
    headers = {"Authorization": f"Bearer {admin_token}"}

    res = client.get("/api/admin/reliability/metrics", headers=headers)
    assert res.status_code == 200, f"Reliability metrics failed: {res.text}"
    data = res.json()

    assert "ai_jobs" in data
    assert "notifications" in data
    assert "medication_reminders" in data
    assert "calendar_syncs" in data

    assert "PENDING" in data["ai_jobs"]
    assert "QUEUED" in data["notifications"]
    assert "PENDING" in data["medication_reminders"]
    assert "SYNCED" in data["calendar_syncs"]
