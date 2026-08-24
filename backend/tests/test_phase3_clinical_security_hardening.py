import pytest
from datetime import date, datetime, time, timedelta, timezone
from app.core.security import create_access_token
from app.models.appointment import Appointment, AppointmentStatus
from app.models.records import (
    AISummary,
    AISummaryType,
    ClinicalNote,
    MedicationReminder,
    Prescription,
    PrescriptionMedication,
    ReminderStatus,
    SymptomForm,
)
from app.models.user import Doctor, DoctorWorkingHours, Patient, User, UserRole


def test_patient_cross_tenant_isolation(client, patient_a, patient_b):
    """Verify that Patient A is strictly blocked from viewing Patient B's profile."""
    token_a = create_access_token(subject=patient_a.id, role=patient_a.role.value)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Attempt to access Patient B's ID
    res = client.get(f"/api/patients/{patient_b.patient.id}", headers=headers_a)
    assert res.status_code == 403
    assert "Access denied" in res.json()["detail"]


def test_doctor_without_clinical_relationship_blocked(client, doctor_user, patient_b):
    """Verify that Doctor cannot inspect a patient unless a formal appointment exists."""
    doc_token = create_access_token(subject=doctor_user.id, role=doctor_user.role.value)
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    res = client.get(f"/api/patients/{patient_b.patient.id}", headers=doc_headers)
    assert res.status_code == 403
    assert "No clinical relationship" in res.json()["detail"]


def test_doctor_with_appointment_can_access_patient(client, doctor_user, patient_a, db_session):
    """Verify that Doctor can access patient record once an appointment is scheduled."""
    doctor = doctor_user.doctor
    patient = patient_a.patient

    app_start = datetime.now(timezone.utc) + timedelta(days=2)
    app = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=app_start,
        end_time=app_start + timedelta(minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(app)
    db_session.commit()

    doc_token = create_access_token(subject=doctor_user.id, role=doctor_user.role.value)
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    res = client.get(f"/api/patients/{patient.id}", headers=doc_headers)
    assert res.status_code == 200
    assert res.json()["email"] == patient_a.email


def test_patient_cannot_author_clinical_notes_or_prescriptions(client, patient_a, doctor_user, db_session):
    """Verify that Patients are forbidden from calling doctor clinical authoring endpoints."""
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

    pat_token = create_access_token(subject=patient_a.id, role=patient_a.role.value)
    pat_headers = {"Authorization": f"Bearer {pat_token}"}

    # 1. Attempt to save clinical notes as patient
    notes_res = client.post(
        f"/api/appointments/{app.id}/clinical-notes",
        json={"notes": "Unauthorized patient note", "diagnosis": "Self-diagnosed"},
        headers=pat_headers,
    )
    assert notes_res.status_code == 403

    # 2. Attempt to write prescription as patient
    rx_res = client.post(
        f"/api/appointments/{app.id}/prescription",
        json={
            "general_instructions": "Self prescribed",
            "medications": [
                {
                    "name": "Antibiotic",
                    "dosage": "500mg",
                    "frequency": "ONCE_DAILY",
                    "start_date": date.today().isoformat(),
                    "end_date": (date.today() + timedelta(days=5)).isoformat(),
                }
            ],
        },
        headers=pat_headers,
    )
    assert rx_res.status_code == 403


def test_cannot_consult_on_cancelled_appointment(client, doctor_user, patient_a, db_session):
    """Verify that consultation cannot be finalized on a cancelled appointment."""
    doctor = doctor_user.doctor
    patient = patient_a.patient

    app_start = datetime.now(timezone.utc) + timedelta(days=1)
    app = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=app_start,
        end_time=app_start + timedelta(minutes=30),
        status=AppointmentStatus.CANCELLED,
    )
    db_session.add(app)
    db_session.commit()

    doc_token = create_access_token(subject=doctor_user.id, role=doctor_user.role.value)
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    # Attempt to complete cancelled appointment
    res = client.post(f"/api/appointments/{app.id}/complete", headers=doc_headers)
    assert res.status_code in [400, 409]
