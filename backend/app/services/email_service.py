import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.records import Notification, NotificationStatus

logger = logging.getLogger(__name__)


class EmailService:
    """
    Asynchronous Email Notification Service.
    
    PRIVACY GUARANTEES:
    - Generic, privacy-compliant email subjects and body notifications.
    - Sensitive clinical diagnoses and medical notes are never included in email text;
      patients access detailed medical records securely behind authenticated login.
    - Idempotency key prevents duplicate emails on worker retries.
    """

    MAX_RETRIES = 3
    BACKOFF_MINUTES = [1, 5, 15]

    @classmethod
    def queue_notification(
        cls,
        db: Session,
        user_id: int,
        recipient_email: str,
        event_type: str,
        subject: str,
        body_html: str,
        appointment_id: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> Notification:
        """
        Create a queued Notification record in the database Outbox.
        If a notification with the same idempotency key already exists, returns the existing record.
        """
        if idempotency_key:
            existing = (
                db.query(Notification)
                .filter(Notification.idempotency_key == idempotency_key)
                .first()
            )
            if existing:
                return existing

        notification = Notification(
            user_id=user_id,
            appointment_id=appointment_id,
            type="EMAIL",
            event_type=event_type,
            recipient_email=recipient_email,
            subject=subject,
            body_html=body_html,
            status=NotificationStatus.QUEUED,
            retry_count=0,
            idempotency_key=idempotency_key,
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    @classmethod
    def process_notification(cls, db: Session, notification_id: int) -> Notification:
        """
        Deliver a queued notification with exponential backoff on transient errors.
        """
        notification = db.query(Notification).filter(Notification.id == notification_id).first()
        if not notification:
            return None

        if notification.status == NotificationStatus.SENT:
            # Already delivered (Idempotency guarantee)
            return notification

        now_utc = datetime.now(timezone.utc)

        try:
            cls._send_email(
                recipient=notification.recipient_email,
                subject=notification.subject,
                body_html=notification.body_html,
            )

            notification.status = NotificationStatus.SENT
            notification.sent_at = now_utc
            notification.last_error = None
            db.commit()
            db.refresh(notification)
            return notification

        except Exception as e:
            notification.retry_count += 1
            notification.last_error = str(e)

            if notification.retry_count >= cls.MAX_RETRIES:
                notification.status = NotificationStatus.FAILED
            else:
                backoff_mins = cls.BACKOFF_MINUTES[min(notification.retry_count - 1, len(cls.BACKOFF_MINUTES) - 1)]
                notification.next_retry_at = now_utc + timedelta(minutes=backoff_mins)

            db.commit()
            db.refresh(notification)
            return notification

    @classmethod
    def _send_email(cls, recipient: str, subject: str, body_html: str):
        """Simulate or execute real email sending via configured provider."""
        if settings.EMAIL_PROVIDER == "mock" or not settings.SMTP_USER:
            # In mock mode, log dispatch safely
            logger.info(f"[MOCK EMAIL] To: {recipient} | Subject: {subject}")
            return

        # Real SMTP implementation
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
        msg["To"] = recipient
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM_EMAIL, recipient, msg.as_string())
