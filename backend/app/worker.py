"""
Celery Worker Definition for Production Asynchronous Task Execution.
Run with: celery -A app.worker.celery_app worker --loglevel=info
"""
import os
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "healthcare_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)


@celery_app.task(name="tasks.generate_previsit_ai")
def task_generate_previsit_ai(appointment_id: int):
    from app.core.database import SessionLocal
    from app.services.ai_service import AIService
    db = SessionLocal()
    try:
        AIService.generate_previsit_summary(db, appointment_id)
    finally:
        db.close()


@celery_app.task(name="tasks.generate_postvisit_ai")
def task_generate_postvisit_ai(appointment_id: int):
    from app.core.database import SessionLocal
    from app.services.ai_service import AIService
    db = SessionLocal()
    try:
        AIService.generate_postvisit_summary(db, appointment_id)
    finally:
        db.close()


@celery_app.task(name="tasks.send_email_notification")
def task_send_email_notification(notification_id: int):
    from app.core.database import SessionLocal
    from app.services.email_service import EmailService
    db = SessionLocal()
    try:
        EmailService.process_notification(db, notification_id)
    finally:
        db.close()


@celery_app.task(name="tasks.sync_calendar_event")
def task_sync_calendar_event(appointment_id: int):
    from app.core.database import SessionLocal
    from app.services.calendar_service import CalendarService
    db = SessionLocal()
    try:
        CalendarService.sync_confirmed_appointment(db, appointment_id)
    finally:
        db.close()
