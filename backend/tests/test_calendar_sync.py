from datetime import datetime, timedelta, timezone
from app.core.crypto import decrypt_token, encrypt_token
from app.models.appointment import Appointment, AppointmentStatus
from app.models.records import CalendarConnectionStatus, CalendarEvent, CalendarSyncStatus, GoogleCalendarToken
from app.services.calendar_service import CalendarService


def test_google_calendar_token_encryption_at_rest(client, patient_a, patient_a_token, db_session):
    """Test OAuth access and refresh tokens are encrypted before database persistence."""
    headers = {"Authorization": f"Bearer {patient_a_token}"}

    # 1. Connect OAuth Callback
    response = client.post("/api/calendar/callback", json={"code": "valid_oauth_auth_code_123"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["connected"] is True

    # 2. Inspect raw database record: tokens MUST NOT be stored in plaintext
    token_record = db_session.query(GoogleCalendarToken).filter(GoogleCalendarToken.user_id == patient_a.id).first()
    assert token_record is not None
    assert "mock_access_token" not in token_record.encrypted_access_token
    assert "mock_refresh_token" not in token_record.encrypted_refresh_token

    # 3. Decryption works in-memory
    decrypted_access = decrypt_token(token_record.encrypted_access_token)
    assert decrypted_access.startswith("mock_access_token")

    # 4. Status API never returns raw or encrypted tokens
    res_status = client.get("/api/calendar/status", headers=headers)
    status_data = res_status.json()
    assert "access_token" not in status_data
    assert "encrypted_access_token" not in status_data
    assert status_data["connected"] is True


def test_calendar_event_sync_on_confirmed_appointment(client, patient_a, doctor_user, db_session):
    """Test creating and updating Google Calendar events."""
    patient = patient_a.patient
    doctor = doctor_user.doctor

    # Set patient calendar as connected
    token_rec = GoogleCalendarToken(
        user_id=patient_a.id,
        encrypted_access_token=encrypt_token("access_123"),
        connection_status=CalendarConnectionStatus.CONNECTED,
    )
    db_session.add(token_rec)

    now_utc = datetime.now(timezone.utc)
    app = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        start_time=now_utc + timedelta(days=3),
        end_time=now_utc + timedelta(days=3, minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(app)
    db_session.commit()

    # 1. Sync Event
    cal_event = CalendarService.sync_confirmed_appointment(db_session, app.id)
    assert cal_event is not None
    assert cal_event.sync_status == CalendarSyncStatus.SYNCED
    assert cal_event.google_event_id is not None
    initial_event_id = cal_event.google_event_id

    # 2. Reschedule & Update (Idempotent update of existing event_id)
    app.start_time = now_utc + timedelta(days=4)
    app.end_time = now_utc + timedelta(days=4, minutes=30)
    db_session.commit()

    updated_event = CalendarService.update_rescheduled_appointment(db_session, app.id)
    assert updated_event.google_event_id == initial_event_id
    assert updated_event.sync_status == CalendarSyncStatus.SYNCED

    # 3. Cancel Appointment Deletes Event
    del_ok = CalendarService.delete_cancelled_appointment(db_session, app.id)
    assert del_ok is True
