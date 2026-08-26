import pytest
from app.core.security import verify_password
from app.models.user import User, UserRole
from scripts.seed_admin import seed_admin


def test_seed_admin_idempotent_and_creates_account(db_session, monkeypatch):
    # Ensure test environment uses test db session
    monkeypatch.setattr("scripts.seed_admin.SessionLocal", lambda: db_session)

    # 1. Clean any existing admin in test session
    db_session.query(User).filter(User.email == "admin@hospital.com").delete()
    db_session.commit()

    # 2. Run seed_admin -> should create admin
    seed_admin()

    admin = db_session.query(User).filter(User.email == "admin@hospital.com").first()
    assert admin is not None
    assert admin.email == "admin@hospital.com"
    assert admin.name == "System Administrator"
    assert admin.role == UserRole.ADMIN
    assert admin.status == "active"
    assert verify_password("AdminPass123!", admin.password_hash)

    # 3. Run seed_admin again -> should be idempotent and not raise error or duplicate
    seed_admin()

    admin_count = db_session.query(User).filter(User.email == "admin@hospital.com").count()
    assert admin_count == 1
