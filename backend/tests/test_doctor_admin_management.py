from datetime import datetime, timedelta, timezone
from app.models.appointment import Appointment, AppointmentStatus


def test_admin_update_doctor_and_status(client, admin_token, doctor_user, db_session):
    """Test admin updating doctor profile fields and toggling active status."""
    doctor = doctor_user.doctor
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Update specialization and slot duration
    update_payload = {
        "specialization": "Pediatric Cardiology",
        "slot_duration": 45,
        "bio": "Updated bio text",
    }
    res1 = client.put(f"/api/admin/doctors/{doctor.id}", json=update_payload, headers=headers)
    assert res1.status_code == 200

    db_session.refresh(doctor)
    assert doctor.specialization == "Pediatric Cardiology"
    assert doctor.slot_duration == 45

    # 2. Deactivate doctor
    res2 = client.patch(
        f"/api/admin/doctors/{doctor.id}/status",
        json={"active": False},
        headers=headers,
    )
    assert res2.status_code == 200
    db_session.refresh(doctor)
    assert doctor.active is False


def test_doctor_complete_and_no_show_actions(
    client, doctor_user, doctor_token, patient_a, db_session
):
    """Test doctor marking appointments as COMPLETED or NO_SHOW."""
    doctor = doctor_user.doctor
    now_utc = datetime.now(timezone.utc)

    # 1. Test COMPLETED
    app1 = Appointment(
        patient_id=patient_a.patient.id,
        doctor_id=doctor.id,
        start_time=now_utc - timedelta(hours=1),
        end_time=now_utc - timedelta(minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    # 2. Test NO_SHOW
    app2 = Appointment(
        patient_id=patient_a.patient.id,
        doctor_id=doctor.id,
        start_time=now_utc - timedelta(hours=2),
        end_time=now_utc - timedelta(hours=1, minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add_all([app1, app2])
    db_session.commit()

    headers = {"Authorization": f"Bearer {doctor_token}"}

    # Mark app1 completed
    res1 = client.post(f"/api/appointments/{app1.id}/complete", headers=headers)
    assert res1.status_code == 200
    assert res1.json()["status"] == "COMPLETED"

    # Mark app2 no-show
    res2 = client.post(f"/api/appointments/{app2.id}/no-show", headers=headers)
    assert res2.status_code == 200
    assert res2.json()["status"] == "NO_SHOW"


def test_doctor_cannot_complete_unassigned_appointment(
    client, admin_token, doctor_user, patient_a, db_session
):
    """Test a doctor cannot mark completion on an appointment assigned to another doctor."""
    from app.core.security import create_access_token, get_password_hash
    from app.models.user import Doctor, User, UserRole

    # Create Doctor B
    user_b = User(
        name="Dr. Doctor B",
        email="doctor_b@hospital.com",
        password_hash=get_password_hash("DocPass123!"),
        role=UserRole.DOCTOR,
        status="active",
    )
    db_session.add(user_b)
    db_session.flush()
    doc_b = Doctor(user_id=user_b.id, specialization="Dermatology", slot_duration=30)
    db_session.add(doc_b)
    db_session.commit()

    token_b = create_access_token(subject=user_b.id, role=user_b.role.value)

    # Create appointment assigned to doctor_user.doctor (not Doctor B)
    now_utc = datetime.now(timezone.utc)
    app = Appointment(
        patient_id=patient_a.patient.id,
        doctor_id=doctor_user.doctor.id,
        start_time=now_utc - timedelta(hours=1),
        end_time=now_utc - timedelta(minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(app)
    db_session.commit()

    headers = {"Authorization": f"Bearer {token_b}"}
    response = client.post(f"/api/appointments/{app.id}/complete", headers=headers)
    assert response.status_code == 403
