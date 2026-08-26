import pytest
from app.core.security import get_password_hash, verify_password
from app.models.user import User, UserRole
from scripts.seed_admin import seed_admin


def test_seed_admin_idempotent_and_creates_account(db_session, monkeypatch):
    monkeypatch.setattr("scripts.seed_admin.SessionLocal", lambda: db_session)
    monkeypatch.delenv("ADMIN_RESET_PASSWORD", raising=False)

    # 1. Clean any existing admin in test session
    db_session.query(User).filter(User.email == "admin@hospital.com").delete()
    db_session.commit()

    # 2. Run seed_admin -> creates default admin
    seed_admin()

    admin = db_session.query(User).filter(User.email == "admin@hospital.com").first()
    assert admin is not None
    assert admin.email == "admin@hospital.com"
    assert admin.name == "System Administrator"
    assert admin.role == UserRole.ADMIN
    assert admin.status == "active"
    assert verify_password("AdminPass123!", admin.password_hash)

    # 3. Run seed_admin again without reset flag -> idempotent, no changes
    seed_admin()
    admin_count = db_session.query(User).filter(User.email == "admin@hospital.com").count()
    assert admin_count == 1


def test_seed_admin_preserves_existing_when_reset_not_requested(db_session, monkeypatch):
    monkeypatch.setattr("scripts.seed_admin.SessionLocal", lambda: db_session)
    monkeypatch.setenv("ADMIN_RESET_PASSWORD", "false")

    # Set up existing admin with custom password
    db_session.query(User).filter(User.email == "admin@hospital.com").delete()
    existing = User(
        name="Existing Admin",
        email="admin@hospital.com",
        password_hash=get_password_hash("CustomOldPass999!"),
        role=UserRole.ADMIN,
        status="active",
    )
    db_session.add(existing)
    db_session.commit()

    # Run seed_admin -> should NOT overwrite password
    seed_admin()

    admin = db_session.query(User).filter(User.email == "admin@hospital.com").first()
    assert verify_password("CustomOldPass999!", admin.password_hash)
    assert not verify_password("AdminPass123!", admin.password_hash)


def test_seed_admin_resets_password_when_flag_enabled_and_preserves_other_users(db_session, monkeypatch):
    monkeypatch.setattr("scripts.seed_admin.SessionLocal", lambda: db_session)
    monkeypatch.setenv("ADMIN_RESET_PASSWORD", "true")

    # Create unrelated patient user
    db_session.query(User).filter(User.email.in_(["admin@hospital.com", "patient_seed_test@example.com"])).delete()
    patient = User(
        name="John Patient",
        email="patient_seed_test@example.com",
        password_hash=get_password_hash("PatientSecret123!"),
        role=UserRole.PATIENT,
        status="active",
    )
    # Create admin with outdated password
    admin = User(
        name="System Administrator",
        email="admin@hospital.com",
        password_hash=get_password_hash("OutdatedHash123!"),
        role=UserRole.ADMIN,
        status="active",
    )
    db_session.add_all([patient, admin])
    db_session.commit()

    # Run seed_admin with reset flag
    seed_admin()

    # Verify admin password updated
    refreshed_admin = db_session.query(User).filter(User.email == "admin@hospital.com").first()
    assert verify_password("AdminPass123!", refreshed_admin.password_hash)
    assert refreshed_admin.role == UserRole.ADMIN
    assert refreshed_admin.status == "active"

    # Verify patient was untouched
    refreshed_patient = db_session.query(User).filter(User.email == "patient_seed_test@example.com").first()
    assert verify_password("PatientSecret123!", refreshed_patient.password_hash)
    assert refreshed_patient.role == UserRole.PATIENT
