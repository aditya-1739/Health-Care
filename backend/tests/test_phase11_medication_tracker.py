import pytest
from datetime import date, datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.models.records import (
    IntakeStatus,
    MedicationIntake,
    MedicationReminder,
    MedicationStatus,
    Prescription,
    PrescriptionMedication,
    PrescriptionStatus,
    ReminderStatus,
)
from app.models.user import Doctor, Patient, User, UserRole
from app.services.medication_service import MedicationService


@pytest.fixture
def medication_test_data(db_session: Session):
    """Set up test doctors, two patients, prescriptions, and reminder schedules."""
    # 1. Doctor
    doc_user = User(
        name="Dr. Sarah Mehta",
        email="dr.mehta.med@hospital.org",
        password_hash=get_password_hash("DoctorPass123!"),
        role=UserRole.DOCTOR,
        status="active",
    )
    db_session.add(doc_user)
    db_session.flush()

    doctor = Doctor(
        user_id=doc_user.id,
        specialization="Cardiology",
        slot_duration=30,
    )
    db_session.add(doctor)
    db_session.flush()

    # 2. Patient A
    pat_user_a = User(
        name="Alice Walker",
        email="alice.walker.med@hospital.org",
        password_hash=get_password_hash("PatientPass123!"),
        role=UserRole.PATIENT,
        status="active",
    )
    db_session.add(pat_user_a)
    db_session.flush()

    patient_a = Patient(user_id=pat_user_a.id, phone="555-0101")
    db_session.add(patient_a)
    db_session.flush()

    # 3. Patient B
    pat_user_b = User(
        name="Bob Martin",
        email="bob.martin.med@hospital.org",
        password_hash=get_password_hash("PatientPass123!"),
        role=UserRole.PATIENT,
        status="active",
    )
    db_session.add(pat_user_b)
    db_session.flush()

    patient_b = Patient(user_id=pat_user_b.id, phone="555-0202")
    db_session.add(patient_b)
    db_session.flush()

    # 4. Create Appointments
    from app.models.appointment import Appointment, AppointmentStatus

    now_utc = datetime.now(timezone.utc)
    today = now_utc.date()

    appt_a = Appointment(
        patient_id=patient_a.id,
        doctor_id=doctor.id,
        start_time=now_utc - timedelta(days=1),
        end_time=now_utc - timedelta(days=1, minutes=-30),
        status=AppointmentStatus.COMPLETED,
    )
    appt_b = Appointment(
        patient_id=patient_b.id,
        doctor_id=doctor.id,
        start_time=now_utc - timedelta(days=1),
        end_time=now_utc - timedelta(days=1, minutes=-30),
        status=AppointmentStatus.COMPLETED,
    )
    db_session.add_all([appt_a, appt_b])
    db_session.flush()

    rx_a = Prescription(
        appointment_id=appt_a.id,
        doctor_id=doctor.id,
        patient_id=patient_a.id,
        status=PrescriptionStatus.ACTIVE,
        general_instructions="Take after meals with water",
    )
    db_session.add(rx_a)
    db_session.flush()

    med1 = PrescriptionMedication(
        prescription_id=rx_a.id,
        name="Paracetamol",
        dosage="650 mg",
        frequency="TWICE_DAILY",
        start_date=today,
        end_date=today + timedelta(days=2),
        instructions="Take with full glass of water",
        status=MedicationStatus.ACTIVE,
    )
    med2 = PrescriptionMedication(
        prescription_id=rx_a.id,
        name="Amoxicillin",
        dosage="500 mg",
        frequency="ONCE_DAILY",
        start_date=today,
        end_date=today + timedelta(days=4),
        instructions="Complete full antibiotic course",
        status=MedicationStatus.ACTIVE,
    )
    db_session.add_all([med1, med2])
    db_session.flush()

    # Generate reminders for Patient A
    reminders_a1 = MedicationService.generate_reminders_for_medication(db_session, med1.id, patient_a.id)
    reminders_a2 = MedicationService.generate_reminders_for_medication(db_session, med2.id, patient_a.id)

    # 5. Prescription for Patient B
    rx_b = Prescription(
        appointment_id=appt_b.id,
        doctor_id=doctor.id,
        patient_id=patient_b.id,
        status=PrescriptionStatus.ACTIVE,
    )
    db_session.add(rx_b)
    db_session.flush()

    med_b = PrescriptionMedication(
        prescription_id=rx_b.id,
        name="Ibuprofen",
        dosage="400 mg",
        frequency="ONCE_DAILY",
        start_date=today,
        end_date=today + timedelta(days=1),
        status=MedicationStatus.ACTIVE,
    )
    db_session.add(med_b)
    db_session.flush()

    reminders_b = MedicationService.generate_reminders_for_medication(db_session, med_b.id, patient_b.id)

    db_session.commit()

    token_a = create_access_token(pat_user_a.id, "PATIENT")
    token_b = create_access_token(pat_user_b.id, "PATIENT")

    return {
        "patient_a": patient_a,
        "patient_b": patient_b,
        "token_a": token_a,
        "token_b": token_b,
        "med1": med1,
        "med2": med2,
        "med_b": med_b,
        "reminders_a1": reminders_a1,
        "reminders_a2": reminders_a2,
        "reminders_b": reminders_b,
    }


def test_next_upcoming_dose_calculation(client: TestClient, db_session: Session, medication_test_data):
    """Test that next_dose correctly identifies the earliest pending dose."""
    token = medication_test_data["token_a"]
    resp = client.get(
        "/api/patients/me/medication-schedule",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["next_dose"] is not None
    assert data["next_dose"]["medication_name"] in ["Paracetamol", "Amoxicillin"]
    assert data["next_dose"]["dosage"] in ["650 mg", "500 mg"]
    assert "scheduled_at" in data["next_dose"]
    assert data["total_active_reminders_count"] > 0


def test_due_now_calculation(client: TestClient, db_session: Session, medication_test_data):
    """Test that a dose scheduled in the past 15 minutes is marked DUE_NOW and prioritized."""
    patient_a = medication_test_data["patient_a"]
    now_utc = datetime.now(timezone.utc)

    # Set one reminder to 10 minutes ago
    rem = (
        db_session.query(MedicationReminder)
        .filter(MedicationReminder.patient_id == patient_a.id)
        .order_by(MedicationReminder.scheduled_at.asc())
        .first()
    )
    rem.scheduled_at = now_utc - timedelta(minutes=10)
    db_session.commit()

    token = medication_test_data["token_a"]
    resp = client.get(
        "/api/patients/me/medication-schedule",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["next_dose"] is not None
    assert data["next_dose"]["reminder_id"] == rem.id
    assert data["next_dose"]["status"] == "DUE_NOW"
    assert data["next_dose"]["is_due"] is True


def test_patient_can_mark_own_dose_as_taken(client: TestClient, db_session: Session, medication_test_data):
    """Patient can mark their own medication reminder as taken."""
    token = medication_test_data["token_a"]
    rem = medication_test_data["reminders_a1"][0]

    resp = client.post(
        f"/api/patients/me/medication-reminders/{rem.id}/taken",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["reminder_id"] == rem.id
    assert data["status"] == "TAKEN"
    assert data["taken_at"] is not None

    # Verify in DB
    intake = (
        db_session.query(MedicationIntake)
        .filter(MedicationIntake.reminder_id == rem.id)
        .first()
    )
    assert intake is not None
    assert intake.status == IntakeStatus.TAKEN
    assert intake.taken_at is not None


def test_patient_cannot_mark_another_patients_dose(client: TestClient, db_session: Session, medication_test_data):
    """Patient B cannot mark Patient A's medication as taken (Strict Data Isolation)."""
    token_b = medication_test_data["token_b"]
    rem_a = medication_test_data["reminders_a1"][0]

    resp = client.post(
        f"/api/patients/me/medication-reminders/{rem_a.id}/taken",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code in [403, 404]


def test_duplicate_taken_request_is_idempotent(client: TestClient, db_session: Session, medication_test_data):
    """Repeated calls to mark taken are idempotent and don't create multiple records."""
    token = medication_test_data["token_a"]
    rem = medication_test_data["reminders_a1"][1]

    # First call
    resp1 = client.post(
        f"/api/patients/me/medication-reminders/{rem.id}/taken",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == 200

    # Second duplicate call
    resp2 = client.post(
        f"/api/patients/me/medication-reminders/{rem.id}/taken",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200

    # Verify only 1 intake row exists for this reminder
    intake_count = (
        db_session.query(MedicationIntake)
        .filter(MedicationIntake.reminder_id == rem.id)
        .count()
    )
    assert intake_count == 1


def test_taken_reminder_excluded_from_next_dose(client: TestClient, db_session: Session, medication_test_data):
    """Once a dose is marked TAKEN, the next dose transitions to the subsequent pending dose."""
    token = medication_test_data["token_a"]
    patient_a = medication_test_data["patient_a"]

    # Get current next dose
    resp1 = client.get(
        "/api/patients/me/medication-schedule",
        headers={"Authorization": f"Bearer {token}"},
    )
    first_next = resp1.json()["next_dose"]
    assert first_next is not None
    rem_id = first_next["reminder_id"]

    # Mark it as taken
    client.post(
        f"/api/patients/me/medication-reminders/{rem_id}/taken",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Get updated schedule
    resp2 = client.get(
        "/api/patients/me/medication-schedule",
        headers={"Authorization": f"Bearer {token}"},
    )
    second_next = resp2.json()["next_dose"]

    if second_next is not None:
        assert second_next["reminder_id"] != rem_id


def test_remaining_dose_calculation_and_progress(client: TestClient, db_session: Session, medication_test_data):
    """Remaining doses decrease when doses are marked TAKEN."""
    token = medication_test_data["token_a"]
    med1 = medication_test_data["med1"]

    resp1 = client.get(
        "/api/patients/me/medication-schedule",
        headers={"Authorization": f"Bearer {token}"},
    )
    active_meds = resp1.json()["active_medications"]
    target_med = next(m for m in active_meds if m["medication_id"] == med1.id)
    initial_remaining = target_med["remaining_doses"]
    assert initial_remaining > 0

    # Mark one dose of med1 as taken
    rem = (
        db_session.query(MedicationReminder)
        .filter(MedicationReminder.prescription_medication_id == med1.id)
        .first()
    )
    client.post(
        f"/api/patients/me/medication-reminders/{rem.id}/taken",
        headers={"Authorization": f"Bearer {token}"},
    )

    resp2 = client.get(
        "/api/patients/me/medication-schedule",
        headers={"Authorization": f"Bearer {token}"},
    )
    active_meds_2 = resp2.json()["active_medications"]
    target_med_2 = next(m for m in active_meds_2 if m["medication_id"] == med1.id)

    assert target_med_2["completed_doses"] == 1
    assert target_med_2["remaining_doses"] == initial_remaining - 1


def test_course_completion(client: TestClient, db_session: Session, medication_test_data):
    """When all doses for a medication are taken, course_completed is True."""
    token = medication_test_data["token_b"]
    med_b = medication_test_data["med_b"]
    reminders_b = medication_test_data["reminders_b"]

    for r in reminders_b:
        client.post(
            f"/api/patients/me/medication-reminders/{r.id}/taken",
            headers={"Authorization": f"Bearer {token}"},
        )

    resp = client.get(
        "/api/patients/me/medication-schedule",
        headers={"Authorization": f"Bearer {token}"},
    )
    active_meds = resp.json()["active_medications"]
    b_med = next(m for m in active_meds if m["medication_id"] == med_b.id)

    assert b_med["remaining_doses"] == 0
    assert b_med["course_completed"] is True


def test_missed_dose_detection(client: TestClient, db_session: Session, medication_test_data):
    """Doses past grace period (e.g. 5 hours ago) without intake are labeled MISSED."""
    patient_a = medication_test_data["patient_a"]
    now_utc = datetime.now(timezone.utc)

    # Set reminder to 6 hours ago
    rem = medication_test_data["reminders_a2"][0]
    rem.scheduled_at = now_utc - timedelta(hours=6)
    db_session.commit()

    token = medication_test_data["token_a"]
    resp = client.get(
        "/api/patients/me/medication-schedule",
        headers={"Authorization": f"Bearer {token}"},
    )
    history = resp.json()["history"]
    missed_item = next((h for h in history if h["reminder_id"] == rem.id), None)

    assert missed_item is not None
    assert missed_item["status"] == "MISSED"


def test_cancelled_reminder_is_ignored(client: TestClient, db_session: Session, medication_test_data):
    """Cancelled reminders are excluded from next_dose and cannot be marked taken."""
    token = medication_test_data["token_a"]
    rem = medication_test_data["reminders_a1"][2]
    rem.status = ReminderStatus.CANCELLED
    db_session.commit()

    # Attempt to mark cancelled reminder
    resp = client.post(
        f"/api/patients/me/medication-reminders/{rem.id}/taken",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    assert "cancelled" in resp.json()["detail"].lower()


def test_adherence_calculation(client: TestClient, db_session: Session, medication_test_data):
    """Adherence percentage is correctly computed based on taken vs total passed doses."""
    token = medication_test_data["token_a"]
    now_utc = datetime.now(timezone.utc)

    # 1 dose taken 5 hours ago
    rem1 = medication_test_data["reminders_a1"][0]
    rem1.scheduled_at = now_utc - timedelta(hours=5)
    db_session.commit()
    client.post(f"/api/patients/me/medication-reminders/{rem1.id}/taken", headers={"Authorization": f"Bearer {token}"})

    # 1 dose missed 8 hours ago
    rem2 = medication_test_data["reminders_a1"][1]
    rem2.scheduled_at = now_utc - timedelta(hours=8)
    db_session.commit()

    resp = client.get(
        "/api/patients/me/medication-schedule",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = resp.json()
    adherence = data["adherence_percentage"]
    assert adherence is not None
    history = data["history"]
    taken_in_history = sum(1 for h in history if h["status"] == "TAKEN")
    missed_in_history = sum(1 for h in history if h["status"] == "MISSED")
    expected_adherence = round((taken_in_history / (taken_in_history + missed_in_history)) * 100, 1)
    assert adherence == expected_adherence
