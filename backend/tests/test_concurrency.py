import concurrent.futures
from datetime import date, datetime, time, timedelta, timezone
from fastapi.testclient import TestClient
from app.core.rate_limit import reset_rate_limiter_state
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models.appointment import Appointment
from app.models.user import DoctorWorkingHours, Patient, User, UserRole


def test_concurrent_simultaneous_booking_on_empty_slot(client, doctor_user, db_session):
    """
    MANDATORY CONCURRENCY TEST:
    10 simultaneous requests from 10 distinct patients attempting to hold the EXACT SAME doctor slot,
    starting from an initial state where NO appointment row exists in the database.

    VERIFICATION GOAL:
    - Exactly ONE request succeeds (201 Created).
    - Exactly 9 requests are rejected with 409 Conflict.
    - Exactly ONE appointment row exists in the database.
    """
    reset_rate_limiter_state()
    doctor = doctor_user.doctor

    # Set doctor working hours for Monday (0) 09:00 to 12:00
    wh = DoctorWorkingHours(
        doctor_id=doctor.id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(12, 0),
    )
    db_session.add(wh)

    # Create 10 distinct patient users with valid JWT tokens
    patient_tokens = []
    for i in range(10):
        user = User(
            name=f"Concurrent Patient {i}",
            email=f"concurrent_patient_{i}@test.com",
            password_hash=get_password_hash("Password123!"),
            role=UserRole.PATIENT,
            status="active",
        )
        db_session.add(user)
        db_session.flush()

        patient = Patient(user_id=user.id, phone=f"555-900{i}")
        db_session.add(patient)
        db_session.flush()

        token = create_access_token(subject=user.id, role=user.role.value)
        patient_tokens.append(token)

    db_session.commit()

    # Target slot on next Monday at 10:00 AM UTC
    today = date.today()
    days_ahead = (0 - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    target_date = today + timedelta(days=days_ahead)
    target_slot_start = datetime.combine(target_date, time(10, 0)).replace(tzinfo=timezone.utc)

    # Ensure NO appointment row exists initially
    initial_count = (
        db_session.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor.id,
            Appointment.start_time == target_slot_start,
        )
        .count()
    )
    assert initial_count == 0

    results = []

    def attempt_hold(token):
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "doctor_id": doctor.id,
            "start_time": target_slot_start.isoformat(),
        }
        res = client.post("/api/appointments/hold", json=payload, headers=headers)
        return res.status_code

    # Fire 10 concurrent threads simultaneously
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_hold, token) for token in patient_tokens]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    # Assertions
    status_201_count = results.count(201)
    status_409_count = results.count(409)

    assert status_201_count == 1, f"Expected exactly 1 success (201), got {status_201_count}. Results: {results}"
    assert status_409_count == 9, f"Expected 9 conflicts (409), got {status_409_count}. Results: {results}"

    # Verify database state has exactly 1 appointment for this slot
    final_count = (
        db_session.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor.id,
            Appointment.start_time == target_slot_start,
        )
        .count()
    )
    assert final_count == 1
