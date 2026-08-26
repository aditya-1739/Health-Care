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
from app.core.security import get_password_hash, verify_password
from app.models.user import User, UserRole

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_admin")


def seed_admin():
    admin_email = os.getenv("ADMIN_EMAIL", "admin@hospital.com").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD", "AdminPass123!")
    admin_name = os.getenv("ADMIN_NAME", "System Administrator").strip()
    reset_requested = os.getenv("ADMIN_RESET_PASSWORD", "false").strip().lower() in ("true", "1", "yes")

    db = SessionLocal()
    try:
        existing_admin = db.query(User).filter(User.email == admin_email).first()
        if existing_admin:
            role_val = existing_admin.role.value if hasattr(existing_admin.role, "value") else str(existing_admin.role)
            is_valid_pass = verify_password(admin_password, existing_admin.password_hash)
            
            logger.info(
                "Admin account found: email=%s, role=%s, status=%s, credentials_valid=%s",
                existing_admin.email,
                role_val,
                existing_admin.status,
                is_valid_pass,
            )

            # Synchronize if password is outdated, role/status needs correction, or reset requested
            if not is_valid_pass or role_val != "ADMIN" or existing_admin.status != "active" or reset_requested:
                existing_admin.password_hash = get_password_hash(admin_password)
                existing_admin.role = UserRole.ADMIN
                existing_admin.status = "active"
                if admin_name and existing_admin.name != admin_name:
                    existing_admin.name = admin_name
                db.commit()
                logger.info("Admin account credentials and role successfully synchronized (%s).", admin_email)
                print(f"[SEED_ADMIN] Admin account credentials and role successfully synchronized ({admin_email}).")
            else:
                logger.info("Admin account exists and credentials are valid (%s). No changes needed.", admin_email)
                print(f"[SEED_ADMIN] Admin account exists and credentials are valid ({admin_email}).")
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
        logger.error("Failed to seed/sync admin account: %s", e, exc_info=True)
        print(f"[SEED_ADMIN] Error creating/syncing admin: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
