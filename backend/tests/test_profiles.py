import pytest
from datetime import date, datetime, timedelta, timezone
from app.core.security import create_access_token, get_password_hash
from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import Doctor, Patient, PatientMedicalProfile, User, UserRole


def test_patient_get_and_update_profile(client, patient_a, patient_a_token, db_session):
    """Verify patient can read and update own basic profile with dynamic age calculation."""
    headers = {"Authorization": f"Bearer {patient_a_token}"}

    # 1. Read profile
    res = client.get("/api/profile/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == patient_a.id
    assert data["email"] == patient_a.email
    assert data["role"] == "PATIENT"

    # 2. Update profile with DOB, phone, address, emergency contact
    dob = date(1995, 5, 20)
    payload = {
        "name": "Updated Alice Name",
        "phone": "+1-555-123-4567",
        "date_of_birth": dob.isoformat(),
        "gender": "Female",
        "address": "123 Health Ave, Suite 4B",
        "emergency_contact_name": "Jane Doe",
        "emergency_contact_phone": "+1-555-987-6543",
    }
    update_res = client.put("/api/profile/me", json=payload, headers=headers)
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["name"] == "Updated Alice Name"
    assert updated_data["phone"] == "+1-555-123-4567"
    assert updated_data["date_of_birth"] == "1995-05-20"
    assert updated_data["gender"] == "Female"
    assert updated_data["address"] == "123 Health Ave, Suite 4B"
    assert updated_data["emergency_contact_name"] == "Jane Doe"
    assert updated_data["emergency_contact_phone"] == "+1-555-987-6543"

    # Verify age is computed dynamically
    today = date.today()
    expected_age = today.year - 1995 - ((today.month, today.day) < (5, 20))
    assert updated_data["age"] == expected_age


def test_patient_medical_profile_crud(client, patient_a, patient_a_token, db_session):
    """Verify patient can create and update sensitive medical profile."""
    headers = {"Authorization": f"Bearer {patient_a_token}"}

    # 1. Read initial medical profile (empty)
    get_res = client.get("/api/profile/me/medical", headers=headers)
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["patient_id"] == patient_a.patient.id
    assert data["blood_group"] is None

    # 2. Save medical profile
    med_payload = {
        "blood_group": "O+",
        "height_cm": 175.5,
        "weight_kg": 72.0,
        "allergies": "Penicillin, Peanuts",
        "chronic_conditions": "Mild Asthma",
        "current_medications": "Albuterol Inhaler as needed",
        "past_surgeries": "Appendectomy (2018)",
        "family_history": "Type 2 Diabetes (Maternal)",
        "medical_notes": "Prefers generic medications.",
    }
    put_res = client.put("/api/profile/me/medical", json=med_payload, headers=headers)
    assert put_res.status_code == 200
    saved = put_res.json()
    assert saved["blood_group"] == "O+"
    assert saved["height_cm"] == 175.5
    assert saved["weight_kg"] == 72.0
    assert saved["allergies"] == "Penicillin, Peanuts"
    assert saved["chronic_conditions"] == "Mild Asthma"

    # 3. Verify persistence
    check_res = client.get("/api/profile/me/medical", headers=headers)
    assert check_res.status_code == 200
    assert check_res.json()["allergies"] == "Penicillin, Peanuts"


def test_medical_profile_validation_rejects_invalid_ranges(client, patient_a_token):
    """Ensure invalid height and weight ranges are rejected by schema."""
    headers = {"Authorization": f"Bearer {patient_a_token}"}

    invalid_height = {"height_cm": 10.0}  # ge=30
    res1 = client.put("/api/profile/me/medical", json=invalid_height, headers=headers)
    assert res1.status_code == 422

    invalid_weight = {"weight_kg": -5.0}  # ge=1
    res2 = client.put("/api/profile/me/medical", json=invalid_weight, headers=headers)
    assert res2.status_code == 422


def test_doctor_profile_get_and_update(client, doctor_user, doctor_token, db_session):
    """Verify doctor can read and update own professional profile."""
    headers = {"Authorization": f"Bearer {doctor_token}"}

    res = client.get("/api/profile/me", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "DOCTOR"
    assert data["specialization"] == doctor_user.doctor.specialization

    # Update doctor bio and phone
    payload = {
        "name": "Dr. Updated Name",
        "phone": "+1-555-888-9999",
        "bio": "Experienced cardiologist with 15+ years of clinical practice.",
        "specialization": "Interventional Cardiology",
    }
    update_res = client.put("/api/profile/me", json=payload, headers=headers)
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["name"] == "Dr. Updated Name"
    assert updated["phone"] == "+1-555-888-9999"
    assert updated["bio"] == "Experienced cardiologist with 15+ years of clinical practice."
    assert updated["specialization"] == "Interventional Cardiology"


def test_medical_data_isolation_between_patients(client, patient_a, patient_a_token, patient_b, db_session):
    """Verify Patient A cannot view Patient B's medical profile."""
    headers_a = {"Authorization": f"Bearer {patient_a_token}"}

    med_b = PatientMedicalProfile(patient_id=patient_b.patient.id, blood_group="AB+", allergies="Aspirin")
    db_session.add(med_b)
    db_session.commit()

    # Patient A attempts to access Patient B's medical profile
    res = client.get(f"/api/patients/{patient_b.patient.id}/medical", headers=headers_a)
    assert res.status_code == 403


def test_doctor_clinical_relationship_access_to_patient_medical_profile(
    client, doctor_user, doctor_token, patient_a, db_session
):
    """Verify Doctor can access patient medical profile only if an appointment exists."""
    headers_doc = {"Authorization": f"Bearer {doctor_token}"}

    # Create medical profile for patient A
    med = PatientMedicalProfile(patient_id=patient_a.patient.id, blood_group="B+", allergies="Sulfa")
    db_session.add(med)
    db_session.commit()

    # 1. Doctor without appointment gets 403 Forbidden
    res1 = client.get(f"/api/patients/{patient_a.patient.id}/medical", headers=headers_doc)
    assert res1.status_code == 403

    # 2. Create appointment between doctor and patient
    now = datetime.now(timezone.utc) + timedelta(days=1)
    appt = Appointment(
        doctor_id=doctor_user.doctor.id,
        patient_id=patient_a.patient.id,
        start_time=now,
        end_time=now + timedelta(minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(appt)
    db_session.commit()

    # 3. Doctor now has clinical relationship -> 200 OK
    res2 = client.get(f"/api/patients/{patient_a.patient.id}/medical", headers=headers_doc)
    assert res2.status_code == 200
    assert res2.json()["blood_group"] == "B+"
    assert res2.json()["allergies"] == "Sulfa"


def test_admin_user_profiles_listing_and_detail(
    client, admin_token, patient_a, doctor_user, db_session
):
    """Verify Admin can list all users and view complete detailed profiles without exposing credentials."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. List users
    res = client.get("/api/admin/users", headers=headers)
    assert res.status_code == 200
    users = res.json()
    assert len(users) >= 2
    emails = [u["email"] for u in users]
    assert patient_a.email in emails
    assert doctor_user.email in emails

    # Ensure no passwords/hashes/tokens are in response
    for u in users:
        assert "password" not in u
        assert "password_hash" not in u
        assert "token" not in u

    # 2. View patient profile as admin
    pat_res = client.get(f"/api/admin/users/{patient_a.id}/profile", headers=headers)
    assert pat_res.status_code == 200
    pat_data = pat_res.json()
    assert pat_data["user"]["id"] == patient_a.id
    assert pat_data["patient"] is not None

    # 3. View doctor profile as admin
    doc_res = client.get(f"/api/admin/users/{doctor_user.id}/profile", headers=headers)
    assert doc_res.status_code == 200
    doc_data = doc_res.json()
    assert doc_data["user"]["id"] == doctor_user.id
    assert doc_data["doctor"] is not None
    assert doc_data["doctor"]["specialization"] == doctor_user.doctor.specialization


def test_change_password_flow(client, patient_a, patient_a_token, db_session):
    """Verify change password validations and authentication flow."""
    headers = {"Authorization": f"Bearer {patient_a_token}"}

    # 1. Wrong current password fails
    bad_current = {
        "current_password": "WrongPassword123!",
        "new_password": "NewValidPassword123!",
        "confirm_password": "NewValidPassword123!",
    }
    res1 = client.post("/api/profile/me/change-password", json=bad_current, headers=headers)
    assert res1.status_code == 400
    assert "Incorrect current password" in res1.json()["detail"]

    # 2. Password mismatch fails
    mismatch = {
        "current_password": "AlicePass123!",
        "new_password": "NewValidPassword123!",
        "confirm_password": "DifferentPassword123!",
    }
    res2 = client.post("/api/profile/me/change-password", json=mismatch, headers=headers)
    assert res2.status_code == 422

    # 3. New password identical to current fails
    same_pwd = {
        "current_password": "AlicePass123!",
        "new_password": "AlicePass123!",
        "confirm_password": "AlicePass123!",
    }
    res3 = client.post("/api/profile/me/change-password", json=same_pwd, headers=headers)
    assert res3.status_code == 400
    assert "must be different" in res3.json()["detail"]

    # 4. Successful password change
    valid_payload = {
        "current_password": "AlicePass123!",
        "new_password": "BrandNewSecretPassword999!",
        "confirm_password": "BrandNewSecretPassword999!",
    }
    res4 = client.post("/api/profile/me/change-password", json=valid_payload, headers=headers)
    assert res4.status_code == 200
    assert "Password changed successfully" in res4.json()["message"]

    # 5. Old password login now fails
    login_old = client.post("/api/auth/login", json={"email": patient_a.email, "password": "AlicePass123!"})
    assert login_old.status_code == 401

    # 6. New password login succeeds
    login_new = client.post("/api/auth/login", json={"email": patient_a.email, "password": "BrandNewSecretPassword999!"})
    assert login_new.status_code == 200
    assert "access_token" in login_new.json()


def test_appointment_history_categorization(client, patient_a, patient_a_token, doctor_user, db_session):
    """Verify appointment history organizes appointments into upcoming, past, and cancelled."""
    headers = {"Authorization": f"Bearer {patient_a_token}"}
    now = datetime.now(timezone.utc)

    # 1. Upcoming appointment
    appt_upcoming = Appointment(
        doctor_id=doctor_user.doctor.id,
        patient_id=patient_a.patient.id,
        start_time=now + timedelta(days=2),
        end_time=now + timedelta(days=2, minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    # 2. Past appointment
    appt_past = Appointment(
        doctor_id=doctor_user.doctor.id,
        patient_id=patient_a.patient.id,
        start_time=now - timedelta(days=5),
        end_time=now - timedelta(days=5, minutes=-30),
        status=AppointmentStatus.COMPLETED,
    )
    # 3. Cancelled appointment
    appt_cancelled = Appointment(
        doctor_id=doctor_user.doctor.id,
        patient_id=patient_a.patient.id,
        start_time=now + timedelta(days=3),
        end_time=now + timedelta(days=3, minutes=30),
        status=AppointmentStatus.CANCELLED,
        cancellation_reason="Patient requested reschedule",
    )
    db_session.add_all([appt_upcoming, appt_past, appt_cancelled])
    db_session.commit()

    res = client.get("/api/profile/me/appointments", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 3
    assert len(data["upcoming"]) >= 1
    assert len(data["past"]) >= 1
    assert len(data["cancelled"]) >= 1

    cancelled_items = [c for c in data["cancelled"] if c["id"] == appt_cancelled.id]
    assert len(cancelled_items) == 1
    assert cancelled_items[0]["cancellation_reason"] == "Patient requested reschedule"


def test_public_doctors_endpoint_does_not_leak_private_profile_data(client, doctor_user, db_session):
    """Verify public doctor search does not expose date of birth, phone, or private medical details."""
    doctor_user.doctor.phone = "+1-555-PRIVATE"
    doctor_user.doctor.date_of_birth = date(1980, 1, 1)
    db_session.commit()

    res = client.get(f"/api/doctors/{doctor_user.doctor.id}")
    assert res.status_code == 200
    data = res.json()
    assert "phone" not in data
    assert "date_of_birth" not in data
    assert "age" not in data
    assert "medical_profile" not in data
