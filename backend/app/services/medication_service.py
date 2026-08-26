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
from app.models.user import Doctor, User


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

    @classmethod
    def record_intake(
        cls,
        db: Session,
        reminder_id: int,
        patient_id: int,
        notes: Optional[str] = None,
    ):
        """
        Record a medication dose as taken.
        Guarantees:
        - Strict patient ownership verification.
        - Idempotent against duplicate requests / retries.
        - Updates or creates MedicationIntake with status TAKEN and taken_at timestamp.
        """
        from app.models.records import MedicationIntake, IntakeStatus

        reminder = (
            db.query(MedicationReminder)
            .filter(MedicationReminder.id == reminder_id)
            .first()
        )
        if not reminder:
            return None

        if reminder.patient_id != patient_id:
            raise PermissionError("Access denied: reminder belongs to another patient")

        if reminder.status == ReminderStatus.CANCELLED:
            raise ValueError("Cannot mark a cancelled reminder as taken")

        intake = (
            db.query(MedicationIntake)
            .filter(MedicationIntake.reminder_id == reminder.id)
            .first()
        )

        if intake and intake.status == IntakeStatus.TAKEN:
            # Idempotent response
            return intake, reminder, False

        now_utc = datetime.now(timezone.utc)
        if not intake:
            intake = MedicationIntake(
                reminder_id=reminder.id,
                patient_id=patient_id,
                scheduled_at=reminder.scheduled_at,
                taken_at=now_utc,
                status=IntakeStatus.TAKEN,
                notes=notes,
            )
            db.add(intake)
        else:
            intake.status = IntakeStatus.TAKEN
            intake.taken_at = now_utc
            if notes:
                intake.notes = notes

        db.commit()
        db.refresh(intake)
        return intake, reminder, True

    @classmethod
    def get_patient_schedule(
        cls,
        db: Session,
        patient_id: int,
        ref_now: Optional[datetime] = None,
        tz_offset_hours: int = 0,
    ):
        """
        Compute structured medication schedule with:
        - next_dose (priority: due now -> upcoming pending)
        - today_doses (chronological doses for today in patient's local timezone)
        - upcoming_doses (next future doses)
        - active_medications (treatment progress, remaining doses)
        - history (taken & missed doses)
        """
        from app.models.records import MedicationIntake, IntakeStatus
        from sqlalchemy.orm import joinedload

        now_utc = ref_now or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        # Query all reminders for the patient
        reminders = (
            db.query(MedicationReminder)
            .options(
                joinedload(MedicationReminder.medication)
                .joinedload(PrescriptionMedication.prescription)
                .joinedload(Prescription.doctor)
                .joinedload(Doctor.user),
                joinedload(MedicationReminder.intake),
            )
            .filter(MedicationReminder.patient_id == patient_id)
            .order_by(MedicationReminder.scheduled_at.asc())
            .all()
        )

        # 1. Compute course progress per PrescriptionMedication
        med_stats = {}
        for r in reminders:
            med_id = r.prescription_medication_id
            if med_id not in med_stats:
                med_obj = r.medication
                doctor_name = None
                if med_obj and med_obj.prescription and med_obj.prescription.doctor:
                    doc = med_obj.prescription.doctor
                    doctor_name = getattr(doc.user, "name", None) if doc.user else getattr(doc, "name", None)
                prescription_id = med_obj.prescription_id if med_obj else 0
                med_stats[med_id] = {
                    "medication_id": med_id,
                    "prescription_id": prescription_id,
                    "name": r.medication_name,
                    "dosage": r.dosage,
                    "frequency": med_obj.frequency if med_obj else "DAILY",
                    "instructions": med_obj.instructions if med_obj else None,
                    "doctor_name": doctor_name,
                    "start_date": med_obj.start_date if med_obj else now_utc.date(),
                    "end_date": med_obj.end_date if med_obj else now_utc.date(),
                    "status": med_obj.status if med_obj else MedicationStatus.ACTIVE,
                    "total_doses": 0,
                    "completed_doses": 0,
                    "remaining_doses": 0,
                    "course_completed": False,
                }

            if r.status != ReminderStatus.CANCELLED:
                med_stats[med_id]["total_doses"] += 1
                if r.intake and r.intake.status == IntakeStatus.TAKEN:
                    med_stats[med_id]["completed_doses"] += 1

        for s in med_stats.values():
            s["remaining_doses"] = max(0, s["total_doses"] - s["completed_doses"])
            s["course_completed"] = (s["total_doses"] > 0 and s["remaining_doses"] == 0)

        # 2. Local Today window calculation
        local_now = now_utc + timedelta(hours=tz_offset_hours)
        today_date = local_now.date()
        today_start_local = datetime.combine(today_date, time(0, 0, 0))
        today_end_local = datetime.combine(today_date, time(23, 59, 59, 999999))
        today_start_utc = (today_start_local - timedelta(hours=tz_offset_hours)).replace(tzinfo=timezone.utc)
        today_end_utc = (today_end_local - timedelta(hours=tz_offset_hours)).replace(tzinfo=timezone.utc)

        # 3. Categorize individual doses
        dose_items = []
        due_candidates = []
        future_candidates = []
        today_items = []
        upcoming_items = []
        history_items = []
        taken_count = 0
        missed_count = 0

        for r in reminders:
            sched = r.scheduled_at if r.scheduled_at.tzinfo else r.scheduled_at.replace(tzinfo=timezone.utc)
            m_stat = med_stats.get(r.prescription_medication_id, {})
            doctor_name = m_stat.get("doctor_name")
            instructions = m_stat.get("instructions")
            freq = m_stat.get("frequency")
            remaining = m_stat.get("remaining_doses", 0)
            total = m_stat.get("total_doses", 0)
            completed = m_stat.get("completed_doses", 0)

            # Determine dose status
            is_taken = bool(r.intake and r.intake.status == IntakeStatus.TAKEN)
            is_cancelled = (r.status == ReminderStatus.CANCELLED)

            if is_taken:
                dose_status = "TAKEN"
                taken_count += 1
            elif is_cancelled:
                dose_status = "CANCELLED"
            elif sched < now_utc - timedelta(hours=4):
                dose_status = "MISSED"
                missed_count += 1
            elif sched <= now_utc:
                dose_status = "DUE_NOW"
            else:
                dose_status = "PENDING"

            item = {
                "reminder_id": r.id,
                "prescription_medication_id": r.prescription_medication_id,
                "medication_name": r.medication_name,
                "dosage": r.dosage,
                "frequency": freq,
                "instructions": instructions,
                "doctor_name": doctor_name,
                "scheduled_at": sched,
                "status": dose_status,
                "is_due": (dose_status == "DUE_NOW"),
                "taken_at": r.intake.taken_at if is_taken else None,
                "doses_remaining": remaining,
                "total_doses": total,
                "completed_doses": completed,
            }

            if not is_cancelled:
                # Next dose candidates
                if dose_status == "DUE_NOW":
                    due_candidates.append(item)
                elif dose_status == "PENDING":
                    future_candidates.append(item)

                # Today doses
                if today_start_utc <= sched <= today_end_utc:
                    today_items.append(item)

                # Upcoming (future doses beyond now)
                if sched > now_utc and not is_taken:
                    upcoming_items.append(item)

                # History
                if is_taken or dose_status == "MISSED" or sched < now_utc:
                    history_items.append(item)

        # Select Next Dose: priority DUE_NOW first, then earliest PENDING
        next_dose = None
        if due_candidates:
            # Earliest due dose
            due_candidates.sort(key=lambda x: x["scheduled_at"])
            next_dose = due_candidates[0]
        elif future_candidates:
            future_candidates.sort(key=lambda x: x["scheduled_at"])
            next_dose = future_candidates[0]

        today_items.sort(key=lambda x: x["scheduled_at"])
        upcoming_items.sort(key=lambda x: x["scheduled_at"])
        history_items.sort(key=lambda x: x["scheduled_at"], reverse=True)

        passed_total = taken_count + missed_count
        adherence_pct = round((taken_count / passed_total) * 100, 1) if passed_total > 0 else None

        active_med_list = list(med_stats.values())
        active_reminders_count = len(due_candidates) + len(future_candidates)

        return {
            "next_dose": next_dose,
            "today_doses": today_items,
            "upcoming_doses": upcoming_items[:10],
            "active_medications": active_med_list,
            "history": history_items[:30],
            "total_active_reminders_count": active_reminders_count,
            "adherence_percentage": adherence_pct,
        }

