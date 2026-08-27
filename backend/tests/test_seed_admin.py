import pytest
from app.core.security import get_password_hash, verify_password
from app.models.user import Patient, User, UserRole
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


def test_seed_admin_syncs_outdated_password_automatically(db_session, monkeypatch):
    monkeypatch.setattr("scripts.seed_admin.SessionLocal", lambda: db_session)

    # Set up existing admin with outdated/unknown password hash
    db_session.query(User).filter(User.email == "admin@hospital.com").delete()
    existing = User(
        name="System Administrator",
        email="admin@hospital.com",
        password_hash=get_password_hash("OutdatedOldHash123!"),
        role=UserRole.ADMIN,
        status="active",
    )
    db_session.add(existing)
    db_session.commit()

    # Run seed_admin -> should detect invalid credentials and synchronize
    seed_admin()

    admin = db_session.query(User).filter(User.email == "admin@hospital.com").first()
    assert verify_password("AdminPass123!", admin.password_hash)
    assert admin.role == UserRole.ADMIN
    assert admin.status == "active"


def test_admin_and_patient_login_endpoints_e2e(client, db_session, monkeypatch):
    monkeypatch.setattr("scripts.seed_admin.SessionLocal", lambda: db_session)

    # Ensure admin is seeded
    db_session.query(User).filter(User.email == "admin@hospital.com").delete()
    seed_admin()

    # 1. Successful Admin Login
    admin_login_res = client.post("/api/auth/login", json={
        "email": "admin@hospital.com",
        "password": "AdminPass123!"
    })
    assert admin_login_res.status_code == 200
    admin_data = admin_login_res.json()
    assert "access_token" in admin_data
    assert admin_data["user"]["role"] == "ADMIN"
    assert admin_data["user"]["email"] == "admin@hospital.com"

    # 2. Failed Admin Login (Wrong Password)
    bad_login_res = client.post("/api/auth/login", json={
        "email": "admin@hospital.com",
        "password": "WrongPassword999!"
    })
    assert bad_login_res.status_code == 401
    assert "Incorrect email or password" in bad_login_res.json()["detail"]

    # 3. Patient Registration & Login
    patient_email = "test_patient_login_flow@hospital.com"
    db_session.query(User).filter(User.email == patient_email).delete()
    db_session.commit()

    reg_res = client.post("/api/auth/register", json={
        "name": "Jane Patient",
        "email": patient_email,
        "password": "PatientPassword123!",
        "phone": "+1234567890"
    })
    assert reg_res.status_code == 201

    patient_login_res = client.post("/api/auth/login", json={
        "email": patient_email,
        "password": "PatientPassword123!"
    })
    assert patient_login_res.status_code == 200
    patient_data = patient_login_res.json()
    assert patient_data["user"]["role"] == "PATIENT"

    # 4. Doctor Login & Role Check
    doctor_email = "test_doctor_auth_flow@hospital.com"
    db_session.query(User).filter(User.email == doctor_email).delete()
    db_session.commit()

    doc_user = User(
        name="Dr. Test Specialist",
        email=doctor_email,
        password_hash=get_password_hash("DoctorPassword123!"),
        role=UserRole.DOCTOR,
        status="active",
    )
    db_session.add(doc_user)
    db_session.commit()

    doc_login_res = client.post("/api/auth/login", json={
        "email": doctor_email,
        "password": "DoctorPassword123!"
    })
    assert doc_login_res.status_code == 200
    doc_data = doc_login_res.json()
    assert doc_data["user"]["role"] == "DOCTOR"

    # 5. Non-Admin (Patient/Doctor) cannot access Admin API Dashboard
    patient_headers = {"Authorization": f"Bearer {patient_data['access_token']}"}
    patient_admin_res = client.get("/api/admin/dashboard", headers=patient_headers)
    assert patient_admin_res.status_code == 403

    doc_headers = {"Authorization": f"Bearer {doc_data['access_token']}"}
    doc_admin_res = client.get("/api/admin/dashboard", headers=doc_headers)
    assert doc_admin_res.status_code == 403

    # 6. Admin can access Admin API Dashboard
    admin_headers = {"Authorization": f"Bearer {admin_data['access_token']}"}
    admin_dash_res = client.get("/api/admin/dashboard", headers=admin_headers)
    assert admin_dash_res.status_code == 200
