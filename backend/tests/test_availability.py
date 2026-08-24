from datetime import date, datetime, time, timedelta, timezone
from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import DoctorLeave, DoctorWorkingHours


def test_doctor_availability_slot_generation(client, doctor_user, db_session):
    """Test standard slot generation according to doctor's working hours and slot duration."""
    doctor = doctor_user.doctor

    # Set working hours: Monday (0) 09:00 to 13:00 (30 min slots -> 8 slots: 09:00, 09:30, 10:00, 10:30, 11:00, 11:30, 12:00, 12:30)
    wh = DoctorWorkingHours(
        doctor_id=doctor.id,
        day_of_week=0,
        start_time=time(9, 0),
        end_time=time(13, 0),
    )
    db_session.add(wh)
    db_session.commit()

    # Choose next Monday
    today = date.today()
    days_ahead = (0 - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_monday = today + timedelta(days=days_ahead)

    response = client.get(f"/api/doctors/{doctor.id}/availability?date={next_monday.isoformat()}")
    assert response.status_code == 200
    data = response.json()
    assert data["doctor_id"] == doctor.id
    assert data["total_slots"] == 8
    assert data["available_slots_count"] == 8
    # Verify 13:00 is not generated as a slot start
    start_times = [s["start_time"] for s in data["slots"]]
    assert any("T09:00:00" in t for t in start_times)
    assert any("T12:30:00" in t for t in start_times)
    assert not any("T13:00:00" in t for t in start_times)


def test_doctor_inactive_returns_no_slots(client, doctor_user, db_session):
    """Test inactive doctor returns 0 available slots."""
    doctor = doctor_user.doctor
    doctor.active = False
    db_session.commit()

    next_monday = date.today() + timedelta(days=7)
    response = client.get(f"/api/doctors/{doctor.id}/availability?date={next_monday.isoformat()}")
    assert response.status_code == 200
    data = response.json()
    assert data["total_slots"] == 0
    assert data["available_slots_count"] == 0


def test_doctor_leave_excludes_slots(client, doctor_user, db_session):
    """Test doctor on leave returns 0 available slots for that date."""
    doctor = doctor_user.doctor
    # Add working hours for Tuesday (1)
    wh = DoctorWorkingHours(
        doctor_id=doctor.id,
        day_of_week=1,
        start_time=time(9, 0),
        end_time=time(12, 0),
    )
    db_session.add(wh)

    # Next Tuesday
    today = date.today()
    days_ahead = (1 - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_tuesday = today + timedelta(days=days_ahead)

    # Add leave covering next Tuesday
    leave = DoctorLeave(
        doctor_id=doctor.id,
        start_date=next_tuesday,
        end_date=next_tuesday,
        reason="Medical conference",
    )
    db_session.add(leave)
    db_session.commit()

    response = client.get(f"/api/doctors/{doctor.id}/availability?date={next_tuesday.isoformat()}")
    assert response.status_code == 200
    data = response.json()
    assert data["total_slots"] == 0
    assert data["available_slots_count"] == 0


def test_availability_accounts_for_appointment_states(client, doctor_user, patient_a, db_session):
    """
    Test active appointments (CONFIRMED, unexpired HELD) mark slot unavailable,
    while historical (COMPLETED, CANCELLED, NO_SHOW, EXPIRED) keep slot available.
    """
    doctor = doctor_user.doctor
    patient = patient_a.patient

    # Working hours Wednesday (2) 09:00 to 11:00 (4 slots: 09:00, 09:30, 10:00, 10:30)
    wh = DoctorWorkingHours(
        doctor_id=doctor.id,
        day_of_week=2,
        start_time=time(9, 0),
        end_time=time(11, 0),
    )
    db_session.add(wh)

    today = date.today()
    days_ahead = (2 - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_wednesday = today + timedelta(days=days_ahead)

    # 1. Confirmed appointment at 09:00
    slot1_start = datetime.combine(next_wednesday, time(9, 0)).replace(tzinfo=timezone.utc)
    slot1_end = slot1_start + timedelta(minutes=30)
    app1 = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=slot1_start,
        end_time=slot1_end,
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(app1)

    # 2. Active HELD appointment at 09:30 (expires in 5 mins)
    slot2_start = datetime.combine(next_wednesday, time(9, 30)).replace(tzinfo=timezone.utc)
    slot2_end = slot2_start + timedelta(minutes=30)
    app2 = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=slot2_start,
        end_time=slot2_end,
        status=AppointmentStatus.HELD,
        hold_expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db_session.add(app2)

    # 3. Expired HELD appointment at 10:00
    slot3_start = datetime.combine(next_wednesday, time(10, 0)).replace(tzinfo=timezone.utc)
    slot3_end = slot3_start + timedelta(minutes=30)
    app3 = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=slot3_start,
        end_time=slot3_end,
        status=AppointmentStatus.HELD,
        hold_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    db_session.add(app3)

    # 4. Cancelled appointment at 10:30
    slot4_start = datetime.combine(next_wednesday, time(10, 30)).replace(tzinfo=timezone.utc)
    slot4_end = slot4_start + timedelta(minutes=30)
    app4 = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=slot4_start,
        end_time=slot4_end,
        status=AppointmentStatus.CANCELLED,
    )
    db_session.add(app4)
    db_session.commit()

    response = client.get(f"/api/doctors/{doctor.id}/availability?date={next_wednesday.isoformat()}")
    assert response.status_code == 200
    data = response.json()
    slots = data["slots"]

    # Slot 09:00 (CONFIRMED) -> False
    assert slots[0]["available"] is False
    # Slot 09:30 (Active HELD) -> False
    assert slots[1]["available"] is False
    # Slot 10:00 (Expired HELD) -> True
    assert slots[2]["available"] is True
    # Slot 10:30 (CANCELLED) -> True
    assert slots[3]["available"] is True
    assert data["available_slots_count"] == 2
