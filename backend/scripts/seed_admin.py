"""
Production-Safe Default Admin Seeding Script.
Idempotently creates the default System Administrator account if it does not already exist.

Usage:
  python scripts/seed_admin.py
"""
import os
import sys
import logging

# Ensure backend directory is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User, UserRole

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_admin")


def seed_admin():
    admin_email = os.getenv("ADMIN_EMAIL", "admin@hospital.com").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD", "AdminPass123!")
    admin_name = os.getenv("ADMIN_NAME", "System Administrator").strip()

    db = SessionLocal()
    try:
        existing_admin = db.query(User).filter(User.email == admin_email).first()
        if existing_admin:
            logger.info("Admin already exists (%s). No action needed.", admin_email)
            print(f"[SEED_ADMIN] Admin already exists ({admin_email}).")
            return

        new_admin = User(
            name=admin_name,
            email=admin_email,
            password_hash=get_password_hash(admin_password),
            role=UserRole.ADMIN,
            status="active",
        )
        db.add(new_admin)
        db.commit()
        logger.info("Default admin created successfully (%s).", admin_email)
        print(f"[SEED_ADMIN] Default admin created successfully ({admin_email}).")

    except Exception as e:
        db.rollback()
        logger.error("Failed to seed admin account: %s", e, exc_info=True)
        print(f"[SEED_ADMIN] Error creating admin: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
