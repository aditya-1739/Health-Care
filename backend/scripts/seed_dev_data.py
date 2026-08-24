"""
Healthcare Appointment Manager — System Seed Script.
Seeds the platform with:
- 1 System Administrator account
- 4 Fictional doctor profiles across key specializations with standard working hours (Mon-Fri 09:00-17:00)
- 0 Patients (patients register themselves via /register)
- 0 Synthetic appointments or medical records (clean operational state)

Usage:
  python backend/scripts/seed_dev_data.py
"""
import os
import sys
from datetime import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import get_password_hash
from app.models.user import Doctor, DoctorWorkingHours, User, UserRole


def seed_system_data():
    print("[SEED] Ensuring database schema is synchronized...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Seed System Administrator
        admin_email = os.getenv("ADMIN_EMAIL", "admin@hospital.com")
        admin_pass = os.getenv("ADMIN_PASSWORD", "AdminPass123!")
        admin_name = os.getenv("ADMIN_NAME", "System Administrator")

        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            admin = User(
                name=admin_name,
                email=admin_email,
                password_hash=get_password_hash(admin_pass),
                role=UserRole.ADMIN,
                status="active",
            )
            db.add(admin)
            print(f"[SEED] Created System Administrator: {admin_email}")
        else:
            # Update name if previously demo
            if admin.name != admin_name:
                admin.name = admin_name
                print(f"[SEED] Updated Administrator name: {admin_name}")

        # 2. Seed 4 Fictional Doctors
        doctors_data = [
            {
                "name": "Dr. Sarah Mehta",
                "email": "sarah.mehta@hospital-care.example",
                "specialization": "Cardiology",
                "bio": "Specialist focused on preventive cardiovascular care and long-term patient wellbeing.",
                "slot_duration": 30,
            },
            {
                "name": "Dr. Arjun Kapoor",
                "email": "arjun.kapoor@hospital-care.example",
                "specialization": "General Medicine",
                "bio": "Experienced primary care physician dedicated to comprehensive diagnostics and family healthcare.",
                "slot_duration": 30,
            },
            {
                "name": "Dr. Neha Sharma",
                "email": "neha.sharma@hospital-care.example",
                "specialization": "Dermatology",
                "bio": "Clinical dermatologist providing modern dermatological care and skin wellness consultations.",
                "slot_duration": 30,
            },
            {
                "name": "Dr. Rohan Malhotra",
                "email": "rohan.malhotra@hospital-care.example",
                "specialization": "Orthopedics",
                "bio": "Orthopedic specialist focusing on joint health, sports mobility, and musculoskeletal recovery.",
                "slot_duration": 30,
            },
        ]

        doc_default_pass = os.getenv("DOCTOR_DEFAULT_PASSWORD", "DoctorPass123!")

        for d in doctors_data:
            doc_user = db.query(User).filter(User.email == d["email"]).first()
            if not doc_user:
                doc_user = User(
                    name=d["name"],
                    email=d["email"],
                    password_hash=get_password_hash(doc_default_pass),
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

                print(f"[SEED] Created Doctor: {d['name']} ({d['specialization']}) - {d['email']}")
            else:
                # Update info if already present
                doc_user.name = d["name"]
                if doc_user.doctor:
                    doc_user.doctor.specialization = d["specialization"]
                    doc_user.doctor.bio = d["bio"]
                    doc_user.doctor.slot_duration = d["slot_duration"]

        db.commit()
        print("[SEED] System initialization completed successfully. Database is clean and operational.")

    except Exception as e:
        db.rollback()
        print(f"[SEED] Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_system_data()
