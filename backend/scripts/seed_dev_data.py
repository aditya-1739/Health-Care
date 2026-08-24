"""
Development Seed Script.
WARNING: This script is intended strictly for local development and testing demonstrations.
It will REFUSE to run if ENVIRONMENT == 'production'.
Run with: python backend/scripts/seed_dev_data.py
"""
import os
import sys
from datetime import date, datetime, time, timedelta, timezone

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import get_password_hash
from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import Doctor, DoctorWorkingHours, Patient, User, UserRole


def seed_development_data():
    if settings.ENVIRONMENT == "production":
        raise RuntimeError(
            "CRITICAL SAFETY CHECK: Seed script cannot be run when ENVIRONMENT=production!"
        )

    print("[SEED] Running database schema creation...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Seed Admin
        admin_email = "admin.demo@hospital.org"
        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            admin = User(
                name="Demo System Administrator",
                email=admin_email,
                password_hash=get_password_hash("AdminDemo123!"),
                role=UserRole.ADMIN,
                status="active",
            )
            db.add(admin)
            print(f"[SEED] Created Admin: {admin_email} / AdminDemo123!")

        # 2. Seed Doctors
        doc_data = [
            {
                "name": "Dr. Alice Smith (Demo)",
                "email": "dr.smith.demo@hospital.org",
                "specialization": "Cardiology",
                "bio": "Cardiology specialist with 12 years clinical experience.",
                "slot_duration": 30,
            },
            {
                "name": "Dr. Robert Jones (Demo)",
                "email": "dr.jones.demo@hospital.org",
                "specialization": "Dermatology",
                "bio": "Certified dermatologist focusing on preventative care.",
                "slot_duration": 30,
            },
        ]

        doctors = []
        for d in doc_data:
            doc_user = db.query(User).filter(User.email == d["email"]).first()
            if not doc_user:
                doc_user = User(
                    name=d["name"],
                    email=d["email"],
                    password_hash=get_password_hash("DoctorDemo123!"),
                    role=UserRole.DOCTOR,
                    status="active",
                )
                db.add(doc_user)
                db.flush()

                doctor = Doctor(
                    user_id=doc_user.id,
                    specialization=d["specialization"],
                    bio=d["bio"],
                    slot_duration=d["slot_duration"],
                    active=True,
                )
                db.add(doctor)
                db.flush()

                # Add Monday - Friday Working Hours (09:00 to 17:00)
                for day in range(5):
                    wh = DoctorWorkingHours(
                        doctor_id=doctor.id,
                        day_of_week=day,
                        start_time=time(9, 0),
                        end_time=time(17, 0),
                    )
                    db.add(wh)

                print(f"[SEED] Created Doctor: {d['email']} / DoctorDemo123!")
                doctors.append(doctor)
            else:
                doctors.append(doc_user.doctor)

        # 3. Seed Patients
        pat_data = [
            {"name": "Alice Green (Demo Patient)", "email": "patient.alice.demo@example.com", "phone": "555-0101"},
            {"name": "Bob White (Demo Patient)", "email": "patient.bob.demo@example.com", "phone": "555-0202"},
        ]

        patients = []
        for p in pat_data:
            pat_user = db.query(User).filter(User.email == p["email"]).first()
            if not pat_user:
                pat_user = User(
                    name=p["name"],
                    email=p["email"],
                    password_hash=get_password_hash("PatientDemo123!"),
                    role=UserRole.PATIENT,
                    status="active",
                )
                db.add(pat_user)
                db.flush()

                patient = Patient(user_id=pat_user.id, phone=p["phone"])
                db.add(patient)
                db.flush()
                print(f"[SEED] Created Patient: {p['email']} / PatientDemo123!")
                patients.append(patient)
            else:
                patients.append(pat_user.patient)

        # 4. Seed sample confirmed appointment
        if doctors and patients:
            sample_start = datetime.now(timezone.utc) + timedelta(days=2, hours=2)
            existing_app = db.query(Appointment).filter(Appointment.doctor_id == doctors[0].id).first()
            if not existing_app:
                app = Appointment(
                    patient_id=patients[0].id,
                    doctor_id=doctors[0].id,
                    start_time=sample_start,
                    end_time=sample_start + timedelta(minutes=30),
                    status=AppointmentStatus.CONFIRMED,
                )
                db.add(app)
                print("[SEED] Created sample confirmed appointment.")

        db.commit()
        print("[SEED] Development database seeding completed successfully.")

    except Exception as e:
        db.rollback()
        print(f"[SEED] Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_development_data()
