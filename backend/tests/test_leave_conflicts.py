from datetime import date, datetime, time, timedelta, timezone
from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import DoctorWorkingHours


def test_doctor_leave_creation_detects_affected_appointments(
    client, doctor_user, doctor_token, patient_a, db_session
):
    """Test doctor scheduling leave detects existing patient bookings and returns them without deleting."""
    doctor = doctor_user.doctor

    today = date.today()
    target_leave_start = today + timedelta(days=10)
    target_leave_end = today + timedelta(days=12)

    # Add appointment on target_leave_start
    slot_start = datetime.combine(target_leave_start, time(10, 0)).replace(tzinfo=timezone.utc)
    slot_end = slot_start + timedelta(minutes=30)
    app = Appointment(
        patient_id=patient_a.patient.id,
        doctor_id=doctor.id,
        start_time=slot_start,
        end_time=slot_end,
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(app)
    db_session.commit()

    headers = {"Authorization": f"Bearer {doctor_token}"}
    payload = {
        "start_date": target_leave_start.isoformat(),
        "end_date": target_leave_end.isoformat(),
        "reason": "Annual Leave",
    }
    response = client.post("/api/doctors/me/leaves", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert "leave" in data
    assert data["leave"]["doctor_id"] == doctor.id
    assert len(data["affected_appointments"]) == 1
    assert data["affected_appointments"][0]["id"] == app.id


def test_smart_alternative_slots_suggestion(
    client, doctor_user, patient_a, patient_a_token, db_session
):
    """Test smart alternative slots recommendation ranks nearby slots."""
    doctor = doctor_user.doctor

    # Add working hours for Monday through Friday 09:00 to 12:00
    for day in range(5):
        wh = DoctorWorkingHours(
            doctor_id=doctor.id,
            day_of_week=day,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )
        db_session.add(wh)

    today = date.today()
    days_ahead = (0 - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    original_date = today + timedelta(days=days_ahead)
    original_start = datetime.combine(original_date, time(10, 0)).replace(tzinfo=timezone.utc)
    original_end = original_start + timedelta(minutes=30)

    app = Appointment(
        patient_id=patient_a.patient.id,
        doctor_id=doctor.id,
        start_time=original_start,
        end_time=original_end,
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(app)
    db_session.commit()

    headers = {"Authorization": f"Bearer {patient_a_token}"}
    response = client.get(f"/api/appointments/{app.id}/alternative-slots", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["appointment_id"] == app.id
    assert len(data["suggestions"]) > 0

    # Ensure suggestions do not include the exact original slot
    for s in data["suggestions"]:
        assert s["start_time"] != original_start.isoformat()
        assert s["doctor_id"] == doctor.id
