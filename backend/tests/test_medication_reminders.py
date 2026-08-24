from datetime import date, datetime, timedelta, timezone
from app.models.records import (
    MedicationReminder,
    MedicationStatus,
    Prescription,
    PrescriptionMedication,
    PrescriptionStatus,
    ReminderStatus,
)
from app.services.medication_service import MedicationService


def test_medication_reminder_schedule_generation_and_boundary(client, patient_a, doctor_user, db_session):
    """Test generating daily medication reminders within start and end date boundary."""
    patient = patient_a.patient
    doctor = doctor_user.doctor

    today = date.today()
    start_date = today
    end_date = today + timedelta(days=3)  # 4 days total (Day 0, 1, 2, 3)

    rx = Prescription(
        appointment_id=101,
        doctor_id=doctor.id,
        patient_id=patient.id,
    )
    db_session.add(rx)
    db_session.flush()

    # TWICE_DAILY -> 2 reminders per day * 4 days = 8 reminders
    med = PrescriptionMedication(
        prescription_id=rx.id,
        name="Metformin",
        dosage="500 mg",
        frequency="TWICE_DAILY",
        start_date=start_date,
        end_date=end_date,
        status=MedicationStatus.ACTIVE,
    )
    db_session.add(med)
    db_session.commit()

    reminders = MedicationService.generate_reminders_for_medication(
        db=db_session,
        medication_id=med.id,
        patient_id=patient.id,
    )

    assert len(reminders) == 8
    for r in reminders:
        assert r.status == ReminderStatus.PENDING
        assert r.medication_name == "Metformin"
        # Ensure no reminder is after end_date + 1 day
        assert r.scheduled_at.date() <= end_date


def test_medication_reminder_idempotent_duplicate_prevention(client, patient_a, doctor_user, db_session):
    """Test executing reminder generation multiple times does not create duplicate reminders."""
    patient = patient_a.patient
    doctor = doctor_user.doctor

    today = date.today()
    rx = Prescription(
        appointment_id=102,
        doctor_id=doctor.id,
        patient_id=patient.id,
    )
    db_session.add(rx)
    db_session.flush()

    med = PrescriptionMedication(
        prescription_id=rx.id,
        name="Lisinopril",
        dosage="10 mg",
        frequency="ONCE_DAILY",
        start_date=today,
        end_date=today + timedelta(days=2),
        status=MedicationStatus.ACTIVE,
    )
    db_session.add(med)
    db_session.commit()

    # 1. First run -> creates 3 reminders
    reminders1 = MedicationService.generate_reminders_for_medication(
        db=db_session,
        medication_id=med.id,
        patient_id=patient.id,
    )
    assert len(reminders1) == 3

    # 2. Second run (worker retry) -> 0 new reminders added
    reminders2 = MedicationService.generate_reminders_for_medication(
        db=db_session,
        medication_id=med.id,
        patient_id=patient.id,
    )
    assert len(reminders2) == 0

    total_count = (
        db_session.query(MedicationReminder)
        .filter(MedicationReminder.prescription_medication_id == med.id)
        .count()
    )
    assert total_count == 3


def test_medication_discontinuation_cancels_future_reminders(client, patient_a, doctor_user, db_session):
    """Test discontinuing a medication cancels future pending reminders."""
    patient = patient_a.patient
    doctor = doctor_user.doctor

    today = date.today()
    rx = Prescription(
        appointment_id=103,
        doctor_id=doctor.id,
        patient_id=patient.id,
    )
    db_session.add(rx)
    db_session.flush()

    med = PrescriptionMedication(
        prescription_id=rx.id,
        name="Atorvastatin",
        dosage="20 mg",
        frequency="ONCE_DAILY",
        start_date=today,
        end_date=today + timedelta(days=5),
        status=MedicationStatus.ACTIVE,
    )
    db_session.add(med)
    db_session.commit()

    MedicationService.generate_reminders_for_medication(
        db=db_session,
        medication_id=med.id,
        patient_id=patient.id,
    )

    # Discontinue medication
    MedicationService.cancel_reminders_for_medication(db_session, med.id)

    pending_count = (
        db_session.query(MedicationReminder)
        .filter(
            MedicationReminder.prescription_medication_id == med.id,
            MedicationReminder.status == ReminderStatus.PENDING,
        )
        .count()
    )
    cancelled_count = (
        db_session.query(MedicationReminder)
        .filter(
            MedicationReminder.prescription_medication_id == med.id,
            MedicationReminder.status == ReminderStatus.CANCELLED,
        )
        .count()
    )
    assert pending_count == 0
    assert cancelled_count > 0
