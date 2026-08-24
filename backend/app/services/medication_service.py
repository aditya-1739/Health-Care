from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.records import (
    MedicationReminder,
    MedicationStatus,
    Prescription,
    PrescriptionMedication,
    PrescriptionStatus,
    ReminderStatus,
)


class MedicationService:
    """
    Medication Reminder Scheduling Engine.
    
    GUARANTEES:
    - Automatically parses structured prescriptions into discrete reminder schedules.
    - Explicit timezone-aware scheduling.
    - Does not generate or send reminders after medication end_date.
    - Idempotency key 'med_rem_{med_id}_{timestamp}' prevents duplicate reminders on worker retry.
    - Discontinuation or cancellation cleanly cancels all future pending reminders.
    """

    DEFAULT_HOURS_MAP = {
        "ONCE_DAILY": [time(9, 0)],
        "TWICE_DAILY": [time(9, 0), time(21, 0)],
        "THREE_TIMES_DAILY": [time(8, 0), time(14, 0), time(20, 0)],
        "EVERY_8_HOURS": [time(6, 0), time(14, 0), time(22, 0)],
        "EVERY_6_HOURS": [time(6, 0), time(12, 0), time(18, 0), time(0, 0)],
        "BEFORE_MEAL": [time(7, 30), time(12, 30), time(18, 30)],
        "AFTER_MEAL": [time(9, 0), time(14, 0), time(20, 0)],
        "BEDTIME": [time(22, 0)],
    }

    @classmethod
    def generate_reminders_for_medication(
        cls,
        db: Session,
        medication_id: int,
        patient_id: int,
        tz_offset_hours: int = 0,
    ) -> List[MedicationReminder]:
        """
        Generate discrete reminder instances for a PrescriptionMedication from start_date to end_date.
        """
        medication = (
            db.query(PrescriptionMedication)
            .filter(PrescriptionMedication.id == medication_id)
            .first()
        )
        if not medication or medication.status != MedicationStatus.ACTIVE:
            return []

        freq_key = medication.frequency.upper().replace(" ", "_")
        reminder_times = cls.DEFAULT_HOURS_MAP.get(freq_key, [time(9, 0)])

        created_reminders = []
        curr_date = medication.start_date
        end_date = medication.end_date

        while curr_date <= end_date:
            for t in reminder_times:
                # Construct local naive datetime and adjust by timezone offset
                local_dt = datetime.combine(curr_date, t)
                # Convert to UTC
                utc_dt = (local_dt - timedelta(hours=tz_offset_hours)).replace(tzinfo=timezone.utc)

                idemp_key = f"med_rem_{medication.id}_{utc_dt.isoformat()}"

                # Check if reminder already exists (Idempotency)
                existing = (
                    db.query(MedicationReminder)
                    .filter(MedicationReminder.idempotency_key == idemp_key)
                    .first()
                )
                if not existing:
                    reminder = MedicationReminder(
                        prescription_medication_id=medication.id,
                        patient_id=patient_id,
                        medication_name=medication.name,
                        dosage=medication.dosage,
                        scheduled_at=utc_dt,
                        status=ReminderStatus.PENDING,
                        idempotency_key=idemp_key,
                    )
                    db.add(reminder)
                    created_reminders.append(reminder)

            curr_date += timedelta(days=1)

        db.commit()
        return created_reminders

    @classmethod
    def cancel_reminders_for_medication(cls, db: Session, medication_id: int):
        """Cancel all pending reminders when medication is discontinued or cancelled."""
        pending_reminders = (
            db.query(MedicationReminder)
            .filter(
                MedicationReminder.prescription_medication_id == medication_id,
                MedicationReminder.status == ReminderStatus.PENDING,
            )
            .all()
        )
        for r in pending_reminders:
            r.status = ReminderStatus.CANCELLED
        db.commit()

    @classmethod
    def cancel_reminders_for_prescription(cls, db: Session, prescription_id: int):
        """Cancel all future pending reminders for an entire prescription."""
        now_utc = datetime.now(timezone.utc)
        prescription = db.query(Prescription).filter(Prescription.id == prescription_id).first()
        if not prescription:
            return

        for med in prescription.medications:
            cls.cancel_reminders_for_medication(db, med.id)
