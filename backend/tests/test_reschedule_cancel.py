from datetime import date, datetime, time, timedelta, timezone
from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import DoctorWorkingHours


def test_cancel_appointment_and_rebook(
    client, doctor_user, patient_a, patient_a_token, db_session
):
    """Test cancelling an appointment sets CANCELLED and allows slot to be booked again."""
    doctor = doctor_user.doctor

    # Set working hours for Tuesday (1) 09:00 to 12:00
    wh = DoctorWorkingHours(
        doctor_id=doctor.id,
        day_of_week=1,
        start_time=time(9, 0),
        end_time=time(12, 0),
    )
    db_session.add(wh)

    today = date.today()
    days_ahead = (1 - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    target_date = today + timedelta(days=days_ahead)
    slot_start = datetime.combine(target_date, time(9, 0)).replace(tzinfo=timezone.utc)
    slot_end = slot_start + timedelta(minutes=30)

    # Create confirmed appointment
    app = Appointment(
        patient_id=patient_a.patient.id,
        doctor_id=doctor.id,
        start_time=slot_start,
        end_time=slot_end,
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(app)
    db_session.commit()

    headers = {"Authorization": f"Bearer {patient_a_token}"}

    # Cancel appointment
    cancel_res = client.post(
        f"/api/appointments/{app.id}/cancel",
        json={"reason": "Schedule conflict"},
        headers=headers,
    )
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.json()
    assert cancel_data["status"] == "CANCELLED"
    assert cancel_data["cancellation_reason"] == "Schedule conflict"
    assert cancel_data["cancelled_at"] is not None

    # Immediate re-hold should now succeed
    rehold_res = client.post(
        "/api/appointments/hold",
        json={"doctor_id": doctor.id, "start_time": slot_start.isoformat()},
        headers=headers,
    )
    assert rehold_res.status_code == 201
    assert rehold_res.json()["status"] == "HELD"


def test_reschedule_appointment_atomic_success(
    client, doctor_user, patient_a, patient_a_token, db_session
):
    """Test atomic rescheduling updates old appointment to RESCHEDULED and creates new CONFIRMED appointment."""
    doctor = doctor_user.doctor

    # Set working hours for Tuesday (1) 09:00 to 12:00
    wh = DoctorWorkingHours(
        doctor_id=doctor.id,
        day_of_week=1,
        start_time=time(9, 0),
        end_time=time(12, 0),
    )
    db_session.add(wh)

    today = date.today()
    days_ahead = (1 - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    target_date = today + timedelta(days=days_ahead)
    old_start = datetime.combine(target_date, time(9, 0)).replace(tzinfo=timezone.utc)
    old_end = old_start + timedelta(minutes=30)
    new_start = datetime.combine(target_date, time(10, 30)).replace(tzinfo=timezone.utc)

    # Original confirmed appointment
    original_app = Appointment(
        patient_id=patient_a.patient.id,
        doctor_id=doctor.id,
        start_time=old_start,
        end_time=old_end,
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(original_app)
    db_session.commit()

    headers = {"Authorization": f"Bearer {patient_a_token}"}
    res = client.post(
        f"/api/appointments/{original_app.id}/reschedule",
        json={"new_start_time": new_start.isoformat()},
        headers=headers,
    )
    assert res.status_code == 200
    new_data = res.json()
    assert new_data["status"] == "CONFIRMED"
    assert new_data["rescheduled_from_id"] == original_app.id

    # Verify old appointment transitioned to RESCHEDULED
    db_session.refresh(original_app)
    assert original_app.status == AppointmentStatus.RESCHEDULED


def test_reschedule_to_occupied_slot_fails_and_preserves_original(
    client, doctor_user, patient_a, patient_b, patient_a_token, db_session
):
    """Test rescheduling into an occupied slot returns 409 and keeps original appointment valid."""
    doctor = doctor_user.doctor

    # Set working hours
    wh = DoctorWorkingHours(
        doctor_id=doctor.id,
        day_of_week=1,
        start_time=time(9, 0),
        end_time=time(12, 0),
    )
    db_session.add(wh)

    today = date.today()
    days_ahead = (1 - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7
    target_date = today + timedelta(days=days_ahead)
    slot1_start = datetime.combine(target_date, time(9, 0)).replace(tzinfo=timezone.utc)
    slot1_end = slot1_start + timedelta(minutes=30)
    slot2_start = datetime.combine(target_date, time(9, 30)).replace(tzinfo=timezone.utc)
    slot2_end = slot2_start + timedelta(minutes=30)

    # Patient A's appointment
    app_a = Appointment(
        patient_id=patient_a.patient.id,
        doctor_id=doctor.id,
        start_time=slot1_start,
        end_time=slot1_end,
        status=AppointmentStatus.CONFIRMED,
    )
    # Patient B's appointment at slot 2
    app_b = Appointment(
        patient_id=patient_b.patient.id,
        doctor_id=doctor.id,
        start_time=slot2_start,
        end_time=slot2_end,
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add_all([app_a, app_b])
    db_session.commit()

    headers = {"Authorization": f"Bearer {patient_a_token}"}
    # Patient A attempts to reschedule to slot 2 (which belongs to B)
    res = client.post(
        f"/api/appointments/{app_a.id}/reschedule",
        json={"new_start_time": slot2_start.isoformat()},
        headers=headers,
    )
    assert res.status_code == 409

    # Verify original appointment is still CONFIRMED
    db_session.refresh(app_a)
    assert app_a.status == AppointmentStatus.CONFIRMED


def test_patient_a_cannot_cancel_patient_b_appointment(
    client, doctor_user, patient_b, patient_a_token, db_session
):
    """Patient A attempting to cancel Patient B's appointment receives 403 Forbidden."""
    doctor = doctor_user.doctor
    now_utc = datetime.now(timezone.utc)
    app_b = Appointment(
        patient_id=patient_b.patient.id,
        doctor_id=doctor.id,
        start_time=now_utc + timedelta(days=2),
        end_time=now_utc + timedelta(days=2, minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(app_b)
    db_session.commit()

    headers = {"Authorization": f"Bearer {patient_a_token}"}
    res = client.post(
        f"/api/appointments/{app_b.id}/cancel",
        json={"reason": "Hacking cancel"},
        headers=headers,
    )
    assert res.status_code == 403
