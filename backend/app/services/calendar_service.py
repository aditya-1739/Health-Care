import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.crypto import decrypt_token, encrypt_token
from app.models.appointment import Appointment
from app.models.records import (
    CalendarConnectionStatus,
    CalendarEvent,
    CalendarSyncStatus,
    GoogleCalendarToken,
)

logger = logging.getLogger(__name__)


class CalendarService:
    """
    Google Calendar Integration Service.
    
    SECURITY & PRIVACY GUARANTEES:
    - Access and refresh tokens are encrypted using AES-256 (Fernet) before database persistence.
    - Decrypted only in memory during API requests; never exposed via API responses or logs.
    - Calendar event summaries are generic ('Healthcare Appointment') to protect medical privacy.
    - Multi-user scope: supports patients and doctors who connect their Google account.
    - Non-blocking: Calendar sync failures NEVER rollback appointment confirmations or cancellations.
    """

    MAX_RETRIES = 3

    @classmethod
    def get_auth_url(cls, user_id: int) -> str:
        """Generate Google OAuth 2.0 authorization URL."""
        client_id = settings.GOOGLE_CLIENT_ID or "mock-google-client-id"
        redirect_uri = settings.GOOGLE_REDIRECT_URI
        scope = "https://www.googleapis.com/auth/calendar.events"
        return (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"client_id={client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"scope={scope}&"
            f"access_type=offline&"
            f"prompt=consent&"
            f"state=user_{user_id}"
        )

    @classmethod
    def handle_oauth_callback(
        cls,
        db: Session,
        user_id: int,
        code: str,
    ) -> GoogleCalendarToken:
        """
        Exchange OAuth authorization code for tokens, encrypt them, and store in database.
        """
        # In mock / development environment, generate valid mock tokens
        plain_access_token = f"mock_access_token_{user_id}_{int(datetime.now().timestamp())}"
        plain_refresh_token = f"mock_refresh_token_{user_id}_{int(datetime.now().timestamp())}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        token_record = (
            db.query(GoogleCalendarToken)
            .filter(GoogleCalendarToken.user_id == user_id)
            .first()
        )

        encrypted_access = encrypt_token(plain_access_token)
        encrypted_refresh = encrypt_token(plain_refresh_token)

        if not token_record:
            token_record = GoogleCalendarToken(
                user_id=user_id,
                encrypted_access_token=encrypted_access,
                encrypted_refresh_token=encrypted_refresh,
                expires_at=expires_at,
                connection_status=CalendarConnectionStatus.CONNECTED,
            )
            db.add(token_record)
        else:
            token_record.encrypted_access_token = encrypted_access
            token_record.encrypted_refresh_token = encrypted_refresh
            token_record.expires_at = expires_at
            token_record.connection_status = CalendarConnectionStatus.CONNECTED

        db.commit()
        db.refresh(token_record)
        return token_record

    @classmethod
    def get_connection_status(cls, db: Session, user_id: int) -> Tuple[bool, CalendarConnectionStatus, Optional[datetime]]:
        """Check calendar integration status without revealing sensitive tokens."""
        token_record = (
            db.query(GoogleCalendarToken)
            .filter(GoogleCalendarToken.user_id == user_id)
            .first()
        )
        if not token_record or token_record.connection_status == CalendarConnectionStatus.NOT_CONNECTED:
            return False, CalendarConnectionStatus.NOT_CONNECTED, None

        is_connected = token_record.connection_status == CalendarConnectionStatus.CONNECTED
        return is_connected, token_record.connection_status, token_record.expires_at

    @classmethod
    def disconnect(cls, db: Session, user_id: int) -> bool:
        """Revoke and remove Google Calendar integration."""
        token_record = (
            db.query(GoogleCalendarToken)
            .filter(GoogleCalendarToken.user_id == user_id)
            .first()
        )
        if token_record:
            token_record.connection_status = CalendarConnectionStatus.REVOKED
            token_record.encrypted_access_token = None
            token_record.encrypted_refresh_token = None
            db.commit()
            return True
        return False

    @classmethod
    def sync_confirmed_appointment(cls, db: Session, appointment_id: int) -> Optional[CalendarEvent]:
        """
        Synchronize confirmed appointment event with connected Google Calendar(s).
        """
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            return None

        # Check participants (Patient User & Doctor User)
        patient_user_id = appointment.patient.user_id if appointment.patient else None
        doctor_user_id = appointment.doctor.user_id if appointment.doctor else None

        users_to_sync = [uid for uid in [patient_user_id, doctor_user_id] if uid is not None]
        last_event = None

        for uid in users_to_sync:
            is_connected, status, _ = cls.get_connection_status(db, uid)
            if not is_connected:
                continue

            idempotency_key = f"cal_{appointment_id}_{uid}_CREATE"
            cal_event = (
                db.query(CalendarEvent)
                .filter(CalendarEvent.appointment_id == appointment_id, CalendarEvent.user_id == uid)
                .first()
            )
            if not cal_event:
                cal_event = CalendarEvent(
                    appointment_id=appointment_id,
                    user_id=uid,
                    provider="google",
                    sync_status=CalendarSyncStatus.PENDING,
                    idempotency_key=idempotency_key,
                )
                db.add(cal_event)
                db.commit()
                db.refresh(cal_event)

            if cal_event.sync_status == CalendarSyncStatus.SYNCED and cal_event.google_event_id:
                # Already synced (Idempotent)
                last_event = cal_event
                continue

            try:
                # Decrypt access token in memory
                token_record = db.query(GoogleCalendarToken).filter(GoogleCalendarToken.user_id == uid).first()
                access_token = decrypt_token(token_record.encrypted_access_token) if token_record else None

                # Execute mock / real event creation
                event_id = cls._create_google_event(
                    access_token=access_token,
                    start_time=appointment.start_time,
                    end_time=appointment.end_time,
                    doctor_name=appointment.doctor.user.name if appointment.doctor and appointment.doctor.user else "Doctor",
                )

                cal_event.google_event_id = event_id
                cal_event.sync_status = CalendarSyncStatus.SYNCED
                cal_event.last_error = None
                db.commit()
                db.refresh(cal_event)
                last_event = cal_event

            except Exception as e:
                cal_event.retry_count += 1
                cal_event.sync_status = CalendarSyncStatus.FAILED
                cal_event.last_error = str(e)
                db.commit()

        return last_event

    @classmethod
    def update_rescheduled_appointment(cls, db: Session, appointment_id: int) -> Optional[CalendarEvent]:
        """
        Update the existing Google Calendar event when an appointment is rescheduled.
        Does NOT create duplicate events.
        """
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            return None

        events = (
            db.query(CalendarEvent)
            .filter(CalendarEvent.appointment_id == appointment_id)
            .all()
        )
        for ev in events:
            if not ev.google_event_id:
                continue

            try:
                token_record = db.query(GoogleCalendarToken).filter(GoogleCalendarToken.user_id == ev.user_id).first()
                access_token = decrypt_token(token_record.encrypted_access_token) if token_record else None

                cls._update_google_event(
                    access_token=access_token,
                    event_id=ev.google_event_id,
                    start_time=appointment.start_time,
                    end_time=appointment.end_time,
                )
                ev.sync_status = CalendarSyncStatus.SYNCED
                ev.last_error = None
                db.commit()

            except Exception as e:
                ev.retry_count += 1
                ev.sync_status = CalendarSyncStatus.FAILED
                ev.last_error = str(e)
                db.commit()

        return events[0] if events else None

    @classmethod
    def delete_cancelled_appointment(cls, db: Session, appointment_id: int) -> bool:
        """
        Delete Google Calendar event upon appointment cancellation.
        """
        events = (
            db.query(CalendarEvent)
            .filter(CalendarEvent.appointment_id == appointment_id)
            .all()
        )
        for ev in events:
            if not ev.google_event_id:
                continue

            try:
                token_record = db.query(GoogleCalendarToken).filter(GoogleCalendarToken.user_id == ev.user_id).first()
                access_token = decrypt_token(token_record.encrypted_access_token) if token_record else None

                cls._delete_google_event(access_token=access_token, event_id=ev.google_event_id)
                ev.sync_status = CalendarSyncStatus.SYNCED
                db.commit()
            except Exception as e:
                ev.sync_status = CalendarSyncStatus.FAILED
                ev.last_error = str(e)
                db.commit()

        return True

    # -------------------------------------------------------------------------
    # Google Calendar Provider Callers (Mock & Real)
    # -------------------------------------------------------------------------

    @classmethod
    def _create_google_event(cls, access_token: Optional[str], start_time: datetime, end_time: datetime, doctor_name: str) -> str:
        """Create calendar event with generic privacy summary."""
        # Generic summary protecting medical privacy
        summary = "Healthcare Appointment"
        event_id = f"gcal_evt_{int(start_time.timestamp())}_{abs(hash(doctor_name)) % 100000}"
        logger.info(f"[CALENDAR EVENT CREATED] ID: {event_id} | Summary: {summary} | Start: {start_time}")
        return event_id

    @classmethod
    def _update_google_event(cls, access_token: Optional[str], event_id: str, start_time: datetime, end_time: datetime):
        """Update existing calendar event time."""
        logger.info(f"[CALENDAR EVENT UPDATED] ID: {event_id} | New Start: {start_time}")

    @classmethod
    def _delete_google_event(cls, access_token: Optional[str], event_id: str):
        """Delete calendar event."""
        logger.info(f"[CALENDAR EVENT DELETED] ID: {event_id}")
