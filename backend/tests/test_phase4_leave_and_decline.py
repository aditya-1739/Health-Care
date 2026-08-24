import pytest
from datetime import date, datetime, time, timedelta, timezone
from app.core.security import create_access_token
from app.models.appointment import Appointment, AppointmentStatus
from app.models.records import AuditLog, Notification
from app.models.user import Doctor, DoctorLeave, DoctorWorkingHours, LeaveStatus, Patient, User, UserRole


def test_doctor_submit_leave_starts_pending_and_does_not_block_availability(client, doctor_user, db_session):
    """
    1. Doctor can submit leave request.
    2. New leave starts as PENDING.
    3. Pending leave does not block availability.
    """
    doctor = doctor_user.doctor
    target_date = date.today() + timedelta(days=10)

    # Configure working hours for that day
    wh = DoctorWorkingHours(
        doctor_id=doctor.id,
        day_of_week=target_date.weekday(),
        start_time=time(9, 0),
        end_time=time(17, 0),
    )
    db_session.add(wh)
    db_session.commit()

    doc_token = create_access_token(subject=doctor_user.id, role=doctor_user.role.value)
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    # Submit leave request
    res = client.post(
        "/api/doctors/me/leaves",
        json={
            "start_date": target_date.isoformat(),
            "end_date": (target_date + timedelta(days=2)).isoformat(),
            "reason": "Attending annual medical conference",
        },
        headers=doc_headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["leave"]["status"] == "PENDING"
    assert data["leave"]["reason"] == "Attending annual medical conference"

    # Verify availability is NOT blocked by PENDING leave
    avail_res = client.get(f"/api/doctors/{doctor.id}/availability?date={target_date.isoformat()}")
    assert avail_res.status_code == 200
    avail_data = avail_res.json()
    assert avail_data["available_slots_count"] > 0


def test_admin_leave_review_approval_and_availability_blocking(client, admin_user, doctor_user, patient_a, db_session):
    """
    4. Admin can view pending leave.
    5. Doctor cannot approve leave.
    6. Patient cannot approve leave.
    7. Admin can approve leave.
    8. Approved leave blocks availability.
    11. Doctor can see admin decision and remarks.
    """
    doctor = doctor_user.doctor
    target_date = date.today() + timedelta(days=15)

    wh = DoctorWorkingHours(
        doctor_id=doctor.id,
        day_of_week=target_date.weekday(),
        start_time=time(9, 0),
        end_time=time(17, 0),
    )
    db_session.add(wh)

    # Doctor creates leave
    leave = DoctorLeave(
        doctor_id=doctor.id,
        start_date=target_date,
        end_date=target_date + timedelta(days=1),
        reason="Family event",
        status=LeaveStatus.PENDING,
        requested_at=datetime.now(timezone.utc),
    )
    db_session.add(leave)
    db_session.commit()

    admin_token = create_access_token(subject=admin_user.id, role=admin_user.role.value)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    doc_token = create_access_token(subject=doctor_user.id, role=doctor_user.role.value)
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    pat_token = create_access_token(subject=patient_a.id, role=patient_a.role.value)
    pat_headers = {"Authorization": f"Bearer {pat_token}"}

    # 4. Admin views pending leaves
    list_res = client.get("/api/admin/leave-requests?status=PENDING", headers=admin_headers)
    assert list_res.status_code == 200
    assert any(l["id"] == leave.id for l in list_res.json())

    # 5. Doctor cannot approve leave
    doc_appr = client.post(f"/api/admin/leave-requests/{leave.id}/approve", json={"remarks": "Self-approved"}, headers=doc_headers)
    assert doc_appr.status_code == 403

    # 6. Patient cannot approve leave
    pat_appr = client.post(f"/api/admin/leave-requests/{leave.id}/approve", json={"remarks": "Approved"}, headers=pat_headers)
    assert pat_appr.status_code == 403

    # 7. Admin approves leave
    appr_res = client.post(
        f"/api/admin/leave-requests/{leave.id}/approve",
        json={"remarks": "Approved by Chief Medical Officer."},
        headers=admin_headers,
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "APPROVED"
    assert appr_res.json()["admin_remarks"] == "Approved by Chief Medical Officer."

    # 8. Approved leave blocks availability
    avail_res = client.get(f"/api/doctors/{doctor.id}/availability?date={target_date.isoformat()}")
    assert avail_res.status_code == 200
    assert avail_res.json()["available_slots_count"] == 0

    # 11. Doctor sees admin decision
    doc_leaves_res = client.get("/api/doctors/me/leaves", headers=doc_headers)
    assert doc_leaves_res.status_code == 200
    my_leave = [l for l in doc_leaves_res.json() if l["id"] == leave.id][0]
    assert my_leave["status"] == "APPROVED"
    assert my_leave["admin_remarks"] == "Approved by Chief Medical Officer."


def test_admin_decline_leave_with_remarks_preserves_availability(client, admin_user, doctor_user, db_session):
    """
    9. Admin can decline leave with remarks.
    10. Declined leave does not block availability.
    """
    doctor = doctor_user.doctor
    target_date = date.today() + timedelta(days=20)

    wh = DoctorWorkingHours(
        doctor_id=doctor.id,
        day_of_week=target_date.weekday(),
        start_time=time(9, 0),
        end_time=time(17, 0),
    )
    db_session.add(wh)

    leave = DoctorLeave(
        doctor_id=doctor.id,
        start_date=target_date,
        end_date=target_date,
        reason="Short trip",
        status=LeaveStatus.PENDING,
        requested_at=datetime.now(timezone.utc),
    )
    db_session.add(leave)
    db_session.commit()

    admin_token = create_access_token(subject=admin_user.id, role=admin_user.role.value)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Attempt decline without remarks -> 400
    dec_fail = client.post(f"/api/admin/leave-requests/{leave.id}/decline", json={"remarks": ""}, headers=admin_headers)
    assert dec_fail.status_code == 400

    # Decline with valid remarks
    dec_res = client.post(
        f"/api/admin/leave-requests/{leave.id}/decline",
        json={"remarks": "Clinic is at minimum staffing capacity on this date."},
        headers=admin_headers,
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["status"] == "DECLINED"

    # Availability is NOT blocked by declined leave
    avail_res = client.get(f"/api/doctors/{doctor.id}/availability?date={target_date.isoformat()}")
    assert avail_res.status_code == 200
    assert avail_res.json()["available_slots_count"] > 0


def test_overlapping_leave_requests_validation(client, doctor_user, db_session):
    """12. Overlapping leave requests return 409 Conflict."""
    doctor = doctor_user.doctor
    start = date.today() + timedelta(days=30)
    end = start + timedelta(days=5)

    leave = DoctorLeave(
        doctor_id=doctor.id,
        start_date=start,
        end_date=end,
        reason="Initial Request",
        status=LeaveStatus.PENDING,
        requested_at=datetime.now(timezone.utc),
    )
    db_session.add(leave)
    db_session.commit()

    doc_token = create_access_token(subject=doctor_user.id, role=doctor_user.role.value)
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    # Attempt to submit overlapping leave (start+2 to end+2)
    res = client.post(
        "/api/doctors/me/leaves",
        json={
            "start_date": (start + timedelta(days=2)).isoformat(),
            "end_date": (end + timedelta(days=2)).isoformat(),
            "reason": "Overlapping Request",
        },
        headers=doc_headers,
    )
    assert res.status_code == 409
    assert "overlapping" in res.json()["detail"].lower()


def test_leave_affecting_appointments_does_not_silently_delete(client, doctor_user, patient_a, admin_user, db_session):
    """
    13. Leave affecting appointments returns affected appointments.
    14. Existing appointments are not silently deleted.
    """
    doctor = doctor_user.doctor
    patient = patient_a.patient

    target_date = date.today() + timedelta(days=25)
    app_start = datetime.combine(target_date, time(10, 0)).replace(tzinfo=timezone.utc)
    app = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=app_start,
        end_time=app_start + timedelta(minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(app)
    db_session.commit()

    doc_token = create_access_token(subject=doctor_user.id, role=doctor_user.role.value)
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    # Doctor requests leave on that date
    res = client.post(
        "/api/doctors/me/leaves",
        json={
            "start_date": target_date.isoformat(),
            "end_date": target_date.isoformat(),
            "reason": "Emergency absence",
        },
        headers=doc_headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert len(data["affected_appointments"]) == 1
    assert data["affected_appointments"][0]["id"] == app.id

    # Verify appointment still exists in DB
    db_app = db_session.query(Appointment).filter(Appointment.id == app.id).first()
    assert db_app is not None
    assert db_app.status == AppointmentStatus.CONFIRMED


def test_doctor_can_decline_assigned_appointment_with_remarks(client, doctor_user, patient_a, db_session):
    """
    15. Assigned doctor can decline appointment.
    16. Doctor must provide remarks.
    21. Declined/cancelled appointment releases slot.
    22. Patient sees updated appointment status.
    23. Notification/outbox record is created.
    24. Audit log is created.
    """
    doctor = doctor_user.doctor
    patient = patient_a.patient

    target_date = date.today() + timedelta(days=5)
    app_start = datetime.combine(target_date, time(11, 0)).replace(tzinfo=timezone.utc)
    app = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=app_start,
        end_time=app_start + timedelta(minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(app)
    db_session.commit()

    doc_token = create_access_token(subject=doctor_user.id, role=doctor_user.role.value)
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    # 16. Decline without remarks fails (422/400)
    fail_res = client.post(f"/api/appointments/{app.id}/decline", json={"remarks": ""}, headers=doc_headers)
    assert fail_res.status_code in [400, 422]

    # 15. Decline with valid remarks
    decline_remarks = "Unexpected clinical emergency in surgery ward."
    res = client.post(
        f"/api/appointments/{app.id}/decline",
        json={"remarks": decline_remarks},
        headers=doc_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "CANCELLED"
    assert data["cancellation_reason"] == decline_remarks
    assert data["cancelled_by_user_id"] == doctor_user.id

    # 22. Patient queries appointment and sees decline
    pat_token = create_access_token(subject=patient_a.id, role=patient_a.role.value)
    pat_headers = {"Authorization": f"Bearer {pat_token}"}

    pat_res = client.get(f"/api/appointments/{app.id}", headers=pat_headers)
    assert pat_res.status_code == 200
    pat_data = pat_res.json()
    assert pat_data["status"] == "CANCELLED"
    assert pat_data["cancellation_reason"] == decline_remarks

    # 23. Outbox notification created
    notif = db_session.query(Notification).filter(Notification.appointment_id == app.id, Notification.event_type == "APPOINTMENT_DECLINED").first()
    assert notif is not None
    assert decline_remarks in notif.body_html

    # 24. Audit log created
    audit = db_session.query(AuditLog).filter(AuditLog.action == "APPOINTMENT_DECLINED", AuditLog.user_id == doctor_user.id).first()
    assert audit is not None


def test_doctor_cannot_decline_unassigned_or_completed_appointment(client, doctor_user, patient_b, db_session):
    """
    17. Another doctor receives 403.
    18. Patient cannot use doctor decline endpoint.
    19. Completed appointment cannot be declined.
    20. Cancelled appointment cannot be declined.
    """
    # Create doctor 2
    doc2_user = User(
        name="Dr. Unassigned",
        email="dr.unassigned@hospital.org",
        password_hash="fake",
        role=UserRole.DOCTOR,
        status="active",
    )
    db_session.add(doc2_user)
    db_session.flush()

    doc2 = Doctor(user_id=doc2_user.id, specialization="Neurology", slot_duration=30)
    db_session.add(doc2)
    db_session.flush()

    patient = patient_b.patient
    app_start = datetime.now(timezone.utc) + timedelta(days=3)
    app = Appointment(
        patient_id=patient.id,
        doctor_id=doc2.id, # Assigned to doc2
        start_time=app_start,
        end_time=app_start + timedelta(minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(app)
    db_session.commit()

    # 17. Doctor 1 tries to decline Doc 2's appointment -> 403
    doc1_token = create_access_token(subject=doctor_user.id, role=doctor_user.role.value)
    doc1_headers = {"Authorization": f"Bearer {doc1_token}"}
    res_403 = client.post(f"/api/appointments/{app.id}/decline", json={"remarks": "Not my appt"}, headers=doc1_headers)
    assert res_403.status_code == 403

    # 18. Patient tries to use doctor decline endpoint -> 403
    pat_token = create_access_token(subject=patient_b.id, role=patient_b.role.value)
    pat_headers = {"Authorization": f"Bearer {pat_token}"}
    res_pat_403 = client.post(f"/api/appointments/{app.id}/decline", json={"remarks": "Patient declining"}, headers=pat_headers)
    assert res_pat_403.status_code == 403

    # 19. Completed appointment cannot be declined -> 409
    app.status = AppointmentStatus.COMPLETED
    db_session.commit()

    doc2_token = create_access_token(subject=doc2_user.id, role=doc2_user.role.value)
    doc2_headers = {"Authorization": f"Bearer {doc2_token}"}
    res_completed_409 = client.post(f"/api/appointments/{app.id}/decline", json={"remarks": "Declining completed"}, headers=doc2_headers)
    assert res_completed_409.status_code == 409

    # 20. Already cancelled appointment cannot be declined -> 409
    app.status = AppointmentStatus.CANCELLED
    db_session.commit()
    res_cancelled_409 = client.post(f"/api/appointments/{app.id}/decline", json={"remarks": "Declining cancelled"}, headers=doc2_headers)
    assert res_cancelled_409.status_code == 409
