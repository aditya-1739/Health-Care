from datetime import date, datetime, time, timedelta, timezone
from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import DoctorWorkingHours


def test_hold_slot_success(client, doctor_user, patient_a, patient_a_token, db_session):
    """Test patient creates a temporary 5-minute hold."""
    doctor = doctor_user.doctor

    # Set working hours for Friday (4) 09:00 to 12:00
    wh = DoctorWorkingHours(
        doctor_id=doctor.id,
        day_of_week=4,
        start_time=time(9, 0),
        end_time=time(12, 0),
    )
    db_session.add(wh)
    db_session.commit()

    today = date.today()
    days_ahead = (4 - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_friday = today + timedelta(days=days_ahead)
    slot_start = datetime.combine(next_friday, time(10, 0)).replace(tzinfo=timezone.utc)

    headers = {"Authorization": f"Bearer {patient_a_token}"}
    payload = {
        "doctor_id": doctor.id,
        "start_time": slot_start.isoformat(),
    }
    response = client.post("/api/appointments/hold", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["doctor_id"] == doctor.id
    assert data["patient_id"] == patient_a.patient.id
    assert data["status"] == "HELD"
    assert "hold_expires_at" in data
    assert data["remaining_seconds"] > 0


def test_confirm_held_appointment(client, doctor_user, patient_a, patient_a_token, db_session):
    """Test patient confirms an active hold."""
    doctor = doctor_user.doctor

    # Setup appointment in HELD status
    now_utc = datetime.now(timezone.utc)
    slot_start = now_utc + timedelta(days=2)
    slot_end = slot_start + timedelta(minutes=30)
    app = Appointment(
        patient_id=patient_a.patient.id,
        doctor_id=doctor.id,
        start_time=slot_start,
        end_time=slot_end,
        status=AppointmentStatus.HELD,
        hold_expires_at=now_utc + timedelta(minutes=5),
    )
    db_session.add(app)
    db_session.commit()

    headers = {"Authorization": f"Bearer {patient_a_token}"}
    response = client.post(f"/api/appointments/{app.id}/confirm", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == app.id
    assert data["status"] == "CONFIRMED"


def test_confirm_expired_hold_is_rejected(client, doctor_user, patient_a, patient_a_token, db_session):
    """Test attempting to confirm an expired hold returns 409 Conflict."""
    doctor = doctor_user.doctor

    now_utc = datetime.now(timezone.utc)
    slot_start = now_utc + timedelta(days=2)
    slot_end = slot_start + timedelta(minutes=30)
    app = Appointment(
        patient_id=patient_a.patient.id,
        doctor_id=doctor.id,
        start_time=slot_start,
        end_time=slot_end,
        status=AppointmentStatus.HELD,
        hold_expires_at=now_utc - timedelta(minutes=1),  # Expired
    )
    db_session.add(app)
    db_session.commit()

    headers = {"Authorization": f"Bearer {patient_a_token}"}
    response = client.post(f"/api/appointments/{app.id}/confirm", headers=headers)
    assert response.status_code == 409
    assert "expired" in response.json()["detail"].lower()


def test_patient_b_cannot_hold_actively_held_slot(
    client, doctor_user, patient_a, patient_b, patient_b_token, db_session
):
    """Test Patient B cannot hold a slot currently held by Patient A."""
    doctor = doctor_user.doctor

    # Add working hours for Thursday (3)
    wh = DoctorWorkingHours(
        doctor_id=doctor.id,
        day_of_week=3,
        start_time=time(9, 0),
        end_time=time(12, 0),
    )
    db_session.add(wh)

    today = date.today()
    days_ahead = (3 - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_thursday = today + timedelta(days=days_ahead)
    slot_start = datetime.combine(next_thursday, time(11, 0)).replace(tzinfo=timezone.utc)
    slot_end = slot_start + timedelta(minutes=30)

    # Patient A holds slot
    app_a = Appointment(
        patient_id=patient_a.patient.id,
        doctor_id=doctor.id,
        start_time=slot_start,
        end_time=slot_end,
        status=AppointmentStatus.HELD,
        hold_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db_session.add(app_a)
    db_session.commit()

    # Patient B attempts to hold same slot
    headers = {"Authorization": f"Bearer {patient_b_token}"}
    payload = {
        "doctor_id": doctor.id,
        "start_time": slot_start.isoformat(),
    }
    response = client.post("/api/appointments/hold", json=payload, headers=headers)
    assert response.status_code == 409
    detail = response.json()["detail"].lower()
    assert "held" in detail or "available" in detail


def test_patient_b_cannot_confirm_patient_a_hold(
    client, doctor_user, patient_a, patient_b_token, db_session
):
    """Test Patient B receives 403 when trying to confirm Patient A's appointment hold."""
    doctor = doctor_user.doctor
    now_utc = datetime.now(timezone.utc)
    slot_start = now_utc + timedelta(days=3)
    slot_end = slot_start + timedelta(minutes=30)

    app = Appointment(
        patient_id=patient_a.patient.id,
        doctor_id=doctor.id,
        start_time=slot_start,
        end_time=slot_end,
        status=AppointmentStatus.HELD,
        hold_expires_at=now_utc + timedelta(minutes=5),
    )
    db_session.add(app)
    db_session.commit()

    headers = {"Authorization": f"Bearer {patient_b_token}"}
    response = client.post(f"/api/appointments/{app.id}/confirm", headers=headers)
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]
