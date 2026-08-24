from unittest.mock import patch
from app.models.records import Notification, NotificationStatus
from app.services.email_service import EmailService


def test_email_notification_queue_and_delivery_success(client, patient_a, db_session):
    """Test creating a queued notification and executing successful delivery."""
    notif = EmailService.queue_notification(
        db=db_session,
        user_id=patient_a.id,
        recipient_email=patient_a.email,
        event_type="BOOKING_CONFIRMATION",
        subject="Your Appointment Confirmation",
        body_html="<p>Your appointment has been confirmed.</p>",
        idempotency_key="notif_test_unique_001",
    )

    assert notif.status == NotificationStatus.QUEUED
    assert notif.retry_count == 0

    # Process notification
    processed = EmailService.process_notification(db_session, notif.id)
    assert processed.status == NotificationStatus.SENT
    assert processed.sent_at is not None


def test_email_notification_retry_on_failure_and_backoff(client, patient_a, db_session):
    """Test transient SMTP failure triggers backoff and increments retry count."""
    notif = EmailService.queue_notification(
        db=db_session,
        user_id=patient_a.id,
        recipient_email=patient_a.email,
        event_type="APPOINTMENT_REMINDER",
        subject="Upcoming Appointment Reminder",
        body_html="<p>Reminder for your upcoming visit.</p>",
        idempotency_key="notif_test_retry_002",
    )

    # Simulate SMTP Connection Error
    with patch.object(EmailService, "_send_email", side_effect=Exception("SMTP Connection Timeout")):
        # Attempt 1
        EmailService.process_notification(db_session, notif.id)
        assert notif.status == NotificationStatus.QUEUED
        assert notif.retry_count == 1
        assert notif.next_retry_at is not None

        # Attempt 2
        EmailService.process_notification(db_session, notif.id)
        assert notif.retry_count == 2

        # Attempt 3 (Final Failure)
        EmailService.process_notification(db_session, notif.id)
        assert notif.status == NotificationStatus.FAILED
        assert notif.retry_count == 3


def test_email_notification_idempotent_duplicate_prevention(client, patient_a, db_session):
    """Test queueing notification with same idempotency key does not insert duplicates."""
    idemp_key = "notif_idemp_key_shared_003"

    notif1 = EmailService.queue_notification(
        db=db_session,
        user_id=patient_a.id,
        recipient_email=patient_a.email,
        event_type="BOOKING_CONFIRMATION",
        subject="Confirmation",
        body_html="<p>Details</p>",
        idempotency_key=idemp_key,
    )

    notif2 = EmailService.queue_notification(
        db=db_session,
        user_id=patient_a.id,
        recipient_email=patient_a.email,
        event_type="BOOKING_CONFIRMATION",
        subject="Confirmation",
        body_html="<p>Details</p>",
        idempotency_key=idemp_key,
    )

    assert notif1.id == notif2.id
    total_count = db_session.query(Notification).filter(Notification.idempotency_key == idemp_key).count()
    assert total_count == 1
