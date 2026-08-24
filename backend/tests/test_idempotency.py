from datetime import date, datetime, time, timedelta, timezone
from app.models.appointment import Appointment
from app.models.user import DoctorWorkingHours


def test_idempotent_hold_request_returns_cached_response(
    client, doctor_user, patient_a, patient_a_token, db_session
):
    """Test re-sending request with same idempotency key returns cached response without duplicate records."""
    doctor = doctor_user.doctor

    # Set working hours for Monday (0)
    wh = DoctorWorkingHours(
        doctor_id=doctor.id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(12, 0),
    )
    db_session.add(wh)
    db_session.commit()

    today = date.today()
    days_ahead = (0 - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    target_date = today + timedelta(days=days_ahead)
    slot_start = datetime.combine(target_date, time(9, 0)).replace(tzinfo=timezone.utc)

    idemp_key = "unique-client-uuid-12345"
    headers = {
        "Authorization": f"Bearer {patient_a_token}",
        "X-Idempotency-Key": idemp_key,
    }
    payload = {
        "doctor_id": doctor.id,
        "start_time": slot_start.isoformat(),
    }

    # 1. First attempt -> 201 Created
    res1 = client.post("/api/appointments/hold", json=payload, headers=headers)
    assert res1.status_code == 201
    data1 = res1.json()
    appointment_id = data1["appointment_id"]

    # 2. Second attempt (retry/double-click) -> returns cached 201 response with same appointment_id
    res2 = client.post("/api/appointments/hold", json=payload, headers=headers)
    assert res2.status_code == 201
    data2 = res2.json()
    assert data2["appointment_id"] == appointment_id

    # Verify only ONE appointment was created in DB
    app_count = db_session.query(Appointment).filter(Appointment.doctor_id == doctor.id).count()
    assert app_count == 1


def test_idempotency_key_reused_with_different_payload_fails(
    client, doctor_user, patient_a, patient_a_token, db_session
):
    """Test reusing the same idempotency key with a differing payload returns 409 Conflict."""
    doctor = doctor_user.doctor

    # Set working hours
    wh = DoctorWorkingHours(
        doctor_id=doctor.id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(12, 0),
    )
    db_session.add(wh)
    db_session.commit()

    today = date.today()
    days_ahead = (0 - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    target_date = today + timedelta(days=days_ahead)
    slot1_start = datetime.combine(target_date, time(9, 30)).replace(tzinfo=timezone.utc)
    slot2_start = datetime.combine(target_date, time(10, 0)).replace(tzinfo=timezone.utc)

    idemp_key = "shared-uuid-different-payload"
    headers = {
        "Authorization": f"Bearer {patient_a_token}",
        "X-Idempotency-Key": idemp_key,
    }

    # 1. First payload
    res1 = client.post(
        "/api/appointments/hold",
        json={"doctor_id": doctor.id, "start_time": slot1_start.isoformat()},
        headers=headers,
    )
    assert res1.status_code == 201

    # 2. Different payload with same key
    res2 = client.post(
        "/api/appointments/hold",
        json={"doctor_id": doctor.id, "start_time": slot2_start.isoformat()},
        headers=headers,
    )
    assert res2.status_code == 409
    assert "different request" in res2.json()["detail"].lower()
