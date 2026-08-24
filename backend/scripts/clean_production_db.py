"""
Database Cleanup & Production Reset Script.
Safely wipes legacy development/demo records in foreign-key order and seeds 4 clean fictional doctors and the system administrator.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal
from app.models.appointment import Appointment
from app.models.records import (
    AISummary,
    AuditLog,
    CalendarEvent,
    ClinicalNote,
    GoogleCalendarToken,
    IdempotencyKey,
    MedicationReminder,
    Notification,
    Prescription,
    PrescriptionMedication,
    SymptomForm,
)
from app.models.user import (
    Doctor,
    DoctorLeave,
    DoctorWorkingHours,
    Patient,
    PatientMedicalProfile,
    User,
)
from scripts.seed_dev_data import seed_system_data


def clean_database():
    db = SessionLocal()
    try:
        print("[CLEANUP] Removing legacy clinical, appointment, and notification records...")
        db.query(MedicationReminder).delete(synchronize_session=False)
        db.query(PrescriptionMedication).delete(synchronize_session=False)
        db.query(Prescription).delete(synchronize_session=False)
        db.query(AISummary).delete(synchronize_session=False)
        db.query(ClinicalNote).delete(synchronize_session=False)
        db.query(SymptomForm).delete(synchronize_session=False)
        db.query(CalendarEvent).delete(synchronize_session=False)
        db.query(GoogleCalendarToken).delete(synchronize_session=False)
        db.query(Notification).delete(synchronize_session=False)
        db.query(IdempotencyKey).delete(synchronize_session=False)
        db.query(DoctorLeave).delete(synchronize_session=False)
        db.query(Appointment).delete(synchronize_session=False)
        db.query(AuditLog).delete(synchronize_session=False)

        print("[CLEANUP] Removing legacy patients and patient medical profiles...")
        db.query(PatientMedicalProfile).delete(synchronize_session=False)
        db.query(Patient).delete(synchronize_session=False)

        print("[CLEANUP] Removing legacy doctor working hours and doctors...")
        db.query(DoctorWorkingHours).delete(synchronize_session=False)
        db.query(Doctor).delete(synchronize_session=False)

        print("[CLEANUP] Removing legacy users...")
        db.query(User).delete(synchronize_session=False)

        db.commit()
        print("[CLEANUP] Database tables wiped cleanly.")
    except Exception as e:
        db.rollback()
        print(f"[CLEANUP] Error wiping tables: {e}")
        raise
    finally:
        db.close()

    print("[CLEANUP] Seeding clean production data...")
    seed_system_data()


if __name__ == "__main__":
    clean_database()
