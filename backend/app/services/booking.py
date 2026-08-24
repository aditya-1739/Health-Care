from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.deps import log_audit
from app.models.appointment import Appointment, AppointmentStatus
from app.models.records import SymptomForm
from app.models.user import Doctor, DoctorLeave, DoctorWorkingHours, Patient, User, UserRole
from app.schemas.appointment import (
    AppointmentHoldRequest,
    AppointmentHoldResponse,
    AppointmentResponse,
)
from app.services.background_tasks import enqueue_task
from app.services.email_service import EmailService
from app.services.locking import acquire_slot_lock
from app.services.medication_service import MedicationService

DEFAULT_HOLD_DURATION_MINUTES = 5


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure a datetime is timezone-aware in UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def hold_slot(
    db: Session,
    patient_user: User,
    payload: AppointmentHoldRequest,
    client_ip: Optional[str] = None,
) -> AppointmentHoldResponse:
    """
    Temporarily hold a doctor appointment slot for 5 minutes.
    Protected against concurrent simultaneous attempts via advisory/resource locking.
    """
    start_time = ensure_utc(payload.start_time)

    # Acquire resource/advisory lock for (doctor_id, start_time) before performing checks
    with acquire_slot_lock(db, payload.doctor_id, start_time.isoformat()):
        patient = patient_user.patient
        if not patient:
            patient = db.query(Patient).filter(Patient.user_id == patient_user.id).first()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient profile not found for this user",
            )

        doctor = db.query(Doctor).filter(Doctor.id == payload.doctor_id).first()
        if not doctor or not doctor.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected doctor is unavailable or inactive",
            )

        slot_duration = doctor.slot_duration or 30
        end_time = start_time + timedelta(minutes=slot_duration)
        now_utc = datetime.now(timezone.utc)

        # 1. Past slot check
        if start_time < now_utc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot book an appointment slot in the past",
            )

        # 2. Doctor leave check
        slot_date = start_time.date()
        on_leave = (
            db.query(DoctorLeave)
            .filter(
                DoctorLeave.doctor_id == doctor.id,
                DoctorLeave.start_date <= slot_date,
                DoctorLeave.end_date >= slot_date,
            )
            .first()
        )
        if on_leave:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Doctor is on leave on the requested date",
            )

        # 3. Doctor working hours check
        day_of_week = slot_date.weekday()
        wh_valid = (
            db.query(DoctorWorkingHours)
            .filter(
                DoctorWorkingHours.doctor_id == doctor.id,
                DoctorWorkingHours.day_of_week == day_of_week,
                DoctorWorkingHours.start_time <= start_time.time(),
                DoctorWorkingHours.end_time >= end_time.time(),
            )
            .first()
        )
        if not wh_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Requested slot is outside doctor's configured working hours",
            )

        # 4. Check active overlapping appointments
        candidate_appointments = (
            db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor.id,
                Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.HELD]),
            )
            .all()
        )

        for app in candidate_appointments:
            app_start = ensure_utc(app.start_time)
            app_end = ensure_utc(app.end_time)
            if app_start < end_time and app_end > start_time:
                if app.status == AppointmentStatus.CONFIRMED:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Slot is no longer available. It is already confirmed.",
                    )
                elif app.status == AppointmentStatus.HELD:
                    hold_exp = ensure_utc(app.hold_expires_at)
                    if hold_exp and hold_exp > now_utc:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Slot is currently held by another patient.",
                        )

        # 5. Create HELD appointment record
        hold_expires_at = now_utc + timedelta(minutes=DEFAULT_HOLD_DURATION_MINUTES)
        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            start_time=start_time,
            end_time=end_time,
            status=AppointmentStatus.HELD,
            hold_expires_at=hold_expires_at,
            idempotency_key=payload.idempotency_key,
        )
        db.add(appointment)
        db.commit()
        db.refresh(appointment)

        log_audit(
            db=db,
            action="APPOINTMENT_HOLD_CREATED",
            resource="appointments",
            user_id=patient_user.id,
            details={
                "appointment_id": appointment.id,
                "doctor_id": doctor.id,
                "start_time": start_time.isoformat(),
                "expires_at": hold_expires_at.isoformat(),
            },
            ip_address=client_ip,
        )

        app_hold_exp = ensure_utc(appointment.hold_expires_at)
        remaining_seconds = max(0, int((app_hold_exp - now_utc).total_seconds()))

        return AppointmentHoldResponse(
            appointment_id=appointment.id,
            doctor_id=doctor.id,
            patient_id=patient.id,
            start_time=ensure_utc(appointment.start_time),
            end_time=ensure_utc(appointment.end_time),
            status=appointment.status,
            hold_expires_at=app_hold_exp,
            remaining_seconds=remaining_seconds,
        )


def confirm_appointment(
    db: Session,
    appointment_id: int,
    patient_user: User,
    idempotency_key: Optional[str] = None,
    client_ip: Optional[str] = None,
) -> AppointmentResponse:
    """
    Confirm a previously HELD appointment within the 5-minute hold window.
    Transition: HELD -> CONFIRMED.
    Dispatches Outbox side-effects (Email, Google Calendar, AI Pre-Visit).
    """
    now_utc = datetime.now(timezone.utc)
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    # Ownership check
    if patient_user.role == UserRole.PATIENT:
        if not patient_user.patient or appointment.patient_id != patient_user.patient.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only confirm your own appointment holds",
            )

    # State Machine check
    if appointment.status == AppointmentStatus.CONFIRMED:
        return _format_appointment_response(appointment)

    if appointment.status != AppointmentStatus.HELD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot confirm appointment with status '{appointment.status.value}'. Must be 'HELD'.",
        )

    # Hold Expiration check
    app_hold_exp = ensure_utc(appointment.hold_expires_at)
    if app_hold_exp and app_hold_exp <= now_utc:
        appointment.status = AppointmentStatus.EXPIRED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Appointment hold has expired. Please select a slot again.",
        )

    app_start = ensure_utc(appointment.start_time)
    with acquire_slot_lock(db, appointment.doctor_id, app_start.isoformat()):
        other_confirmed = (
            db.query(Appointment)
            .filter(
                Appointment.doctor_id == appointment.doctor_id,
                Appointment.id != appointment.id,
                Appointment.status == AppointmentStatus.CONFIRMED,
            )
            .all()
        )
        app_end = ensure_utc(appointment.end_time)
        for other in other_confirmed:
            o_start = ensure_utc(other.start_time)
            o_end = ensure_utc(other.end_time)
            if o_start < app_end and o_end > app_start:
                appointment.status = AppointmentStatus.CANCELLED
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Slot conflict: Another appointment was already confirmed for this time.",
                )

        appointment.status = AppointmentStatus.CONFIRMED
        if idempotency_key:
            appointment.idempotency_key = idempotency_key

        # Outbox Pattern: Create internal notification record within same transaction
        patient_email = patient_user.email
        notif = EmailService.queue_notification(
            db=db,
            user_id=patient_user.id,
            recipient_email=patient_email,
            event_type="BOOKING_CONFIRMATION",
            subject="Appointment Confirmation",
            body_html=f"<p>Hello,</p><p>Your healthcare appointment on {app_start.strftime('%Y-%m-%d %H:%M UTC')} is confirmed.</p>",
            appointment_id=appointment.id,
            idempotency_key=f"notif_{appointment.id}_CONFIRM",
        )

        db.commit()
        db.refresh(appointment)

        log_audit(
            db=db,
            action="APPOINTMENT_CONFIRMED",
            resource="appointments",
            user_id=patient_user.id,
            details={
                "appointment_id": appointment.id,
                "doctor_id": appointment.doctor_id,
                "start_time": app_start.isoformat(),
            },
            ip_address=client_ip,
        )

        # Async Side-effects dispatched non-blockingly
        if notif:
            enqueue_task("SEND_EMAIL_NOTIFICATION", {"notification_id": notif.id})
        enqueue_task("SYNC_CALENDAR_EVENT", {"appointment_id": appointment.id})

        # Check if symptoms were submitted before confirmation
        symptom_form = db.query(SymptomForm).filter(SymptomForm.appointment_id == appointment.id).first()
        if symptom_form:
            enqueue_task("GENERATE_PREVISIT_AI", {"appointment_id": appointment.id})

        return _format_appointment_response(appointment)


def cancel_appointment(
    db: Session,
    appointment_id: int,
    user: User,
    reason: Optional[str] = None,
    client_ip: Optional[str] = None,
) -> AppointmentResponse:
    """
    Cancel an appointment and free the slot for future bookings.
    Transition: CONFIRMED or HELD -> CANCELLED.
    """
    now_utc = datetime.now(timezone.utc)
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    # Ownership / Authorization
    if user.role == UserRole.PATIENT:
        if not user.patient or appointment.patient_id != user.patient.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only cancel your own appointments",
            )
    elif user.role == UserRole.DOCTOR:
        if not user.doctor or appointment.doctor_id != user.doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only cancel appointments assigned to you",
            )

    if appointment.status not in (AppointmentStatus.CONFIRMED, AppointmentStatus.HELD):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel appointment with status '{appointment.status.value}'.",
        )

    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancellation_reason = reason
    appointment.cancelled_by_user_id = user.id
    appointment.cancelled_at = now_utc

    # Outbox: Queue cancellation notification
    patient_email = appointment.patient.user.email if appointment.patient and appointment.patient.user else user.email
    notif = EmailService.queue_notification(
        db=db,
        user_id=appointment.patient.user_id if appointment.patient else user.id,
        recipient_email=patient_email,
        event_type="CANCELLATION",
        subject="Appointment Cancelled",
        body_html=f"<p>Your appointment on {ensure_utc(appointment.start_time).strftime('%Y-%m-%d')} has been cancelled.</p>",
        appointment_id=appointment.id,
        idempotency_key=f"notif_{appointment.id}_CANCEL",
    )

    db.commit()
    db.refresh(appointment)

    log_audit(
        db=db,
        action="APPOINTMENT_CANCELLED",
        resource="appointments",
        user_id=user.id,
        details={
            "appointment_id": appointment.id,
            "reason": reason,
            "cancelled_by": user.role.value,
        },
        ip_address=client_ip,
    )

    # Async side-effects
    if notif:
        enqueue_task("SEND_EMAIL_NOTIFICATION", {"notification_id": notif.id})
    enqueue_task("DELETE_CALENDAR_EVENT", {"appointment_id": appointment.id})

    return _format_appointment_response(appointment)


def decline_appointment(
    db: Session,
    appointment_id: int,
    user: User,
    remarks: str,
    client_ip: Optional[str] = None,
) -> AppointmentResponse:
    """
    Doctor declines an assigned appointment and frees the slot.
    Sets status to CANCELLED, records doctor remarks, and notifies the patient.
    """
    now_utc = datetime.now(timezone.utc)
    if not remarks or not remarks.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decline remarks are required.",
        )

    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    # Ownership / Authorization
    if user.role != UserRole.DOCTOR or not user.doctor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Only doctors can decline appointments",
        )

    if appointment.doctor_id != user.doctor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this appointment.",
        )

    if appointment.status not in (AppointmentStatus.CONFIRMED, AppointmentStatus.HELD):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Appointment is no longer available for decline.",
        )

    clean_remarks = remarks.strip()
    appointment.status = AppointmentStatus.CANCELLED
    appointment.cancellation_reason = clean_remarks
    appointment.cancelled_by_user_id = user.id
    appointment.cancelled_at = now_utc

    # Outbox: Notify patient of doctor decline
    doctor_name = user.name
    appt_date_str = ensure_utc(appointment.start_time).strftime('%Y-%m-%d %H:%M UTC')
    patient_email = appointment.patient.user.email if appointment.patient and appointment.patient.user else user.email
    notif = EmailService.queue_notification(
        db=db,
        user_id=appointment.patient.user_id if appointment.patient else user.id,
        recipient_email=patient_email,
        event_type="APPOINTMENT_DECLINED",
        subject=f"Appointment Declined by {doctor_name}",
        body_html=(
            f"<p>Your appointment on <strong>{appt_date_str}</strong> was declined by {doctor_name}.</p>"
            f"<p><strong>Reason:</strong> {clean_remarks}</p>"
            f"<p>Please log in to your dashboard to select another available appointment slot.</p>"
        ),
        appointment_id=appointment.id,
        idempotency_key=f"notif_{appointment.id}_DECLINE",
    )

    db.commit()
    db.refresh(appointment)

    log_audit(
        db=db,
        action="APPOINTMENT_DECLINED",
        resource="appointments",
        user_id=user.id,
        details={
            "appointment_id": appointment.id,
            "doctor_id": user.doctor.id,
            "remarks": clean_remarks,
        },
        ip_address=client_ip,
    )

    # Async side-effects
    if notif:
        enqueue_task("SEND_EMAIL_NOTIFICATION", {"notification_id": notif.id})
    enqueue_task("DELETE_CALENDAR_EVENT", {"appointment_id": appointment.id})

    return _format_appointment_response(appointment)


def reschedule_appointment(
    db: Session,
    appointment_id: int,
    user: User,
    new_start_time: datetime,
    idempotency_key: Optional[str] = None,
    client_ip: Optional[str] = None,
) -> AppointmentResponse:
    """
    Atomically reschedule an existing appointment to a new slot.
    Original appointment transitions to RESCHEDULED.
    New appointment created as CONFIRMED.
    """
    now_utc = datetime.now(timezone.utc)
    new_start_time = ensure_utc(new_start_time)

    if new_start_time < now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reschedule to a past time slot",
        )

    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    # Authorization
    if user.role == UserRole.PATIENT:
        if not user.patient or appointment.patient_id != user.patient.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only reschedule your own appointments",
            )
    elif user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Insufficient privileges to reschedule appointment",
        )

    if appointment.status != AppointmentStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only CONFIRMED appointments can be rescheduled. Current status: '{appointment.status.value}'.",
        )

    doctor = appointment.doctor
    slot_duration = doctor.slot_duration or 30
    new_end_time = new_start_time + timedelta(minutes=slot_duration)
    target_date = new_start_time.date()

    # Check leave
    on_leave = (
        db.query(DoctorLeave)
        .filter(
            DoctorLeave.doctor_id == doctor.id,
            DoctorLeave.start_date <= target_date,
            DoctorLeave.end_date >= target_date,
        )
        .first()
    )
    if on_leave:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Doctor is on leave on the selected reschedule date",
        )

    # Check working hours
    wh_valid = (
        db.query(DoctorWorkingHours)
        .filter(
            DoctorWorkingHours.doctor_id == doctor.id,
            DoctorWorkingHours.day_of_week == target_date.weekday(),
            DoctorWorkingHours.start_time <= new_start_time.time(),
            DoctorWorkingHours.end_time >= new_end_time.time(),
        )
        .first()
    )
    if not wh_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected slot is outside doctor's configured working hours",
        )

    # Atomic transactional reschedule with lock
    with acquire_slot_lock(db, doctor.id, new_start_time.isoformat()):
        existing = (
            db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor.id,
                Appointment.id != appointment.id,
                Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.HELD]),
            )
            .all()
        )
        for other in existing:
            o_start = ensure_utc(other.start_time)
            o_end = ensure_utc(other.end_time)
            if o_start < new_end_time and o_end > new_start_time:
                if other.status == AppointmentStatus.CONFIRMED:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Selected new slot is already booked.",
                    )
                elif other.status == AppointmentStatus.HELD:
                    hold_exp = ensure_utc(other.hold_expires_at)
                    if hold_exp and hold_exp > now_utc:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Selected new slot is currently held by another patient.",
                        )

        # Transition original appointment
        appointment.status = AppointmentStatus.RESCHEDULED

        # Create new confirmed appointment
        new_appointment = Appointment(
            patient_id=appointment.patient_id,
            doctor_id=doctor.id,
            start_time=new_start_time,
            end_time=new_end_time,
            status=AppointmentStatus.CONFIRMED,
            rescheduled_from_id=appointment.id,
            idempotency_key=idempotency_key,
        )
        db.add(new_appointment)

        # Outbox: Queue reschedule notification
        patient_email = appointment.patient.user.email if appointment.patient and appointment.patient.user else user.email
        notif = EmailService.queue_notification(
            db=db,
            user_id=appointment.patient.user_id if appointment.patient else user.id,
            recipient_email=patient_email,
            event_type="RESCHEDULE",
            subject="Appointment Rescheduled",
            body_html=f"<p>Your appointment has been rescheduled to {new_start_time.strftime('%Y-%m-%d %H:%M UTC')}.</p>",
            appointment_id=new_appointment.id,
            idempotency_key=f"notif_{new_appointment.id}_RESCHEDULE",
        )

        db.commit()
        db.refresh(new_appointment)

        log_audit(
            db=db,
            action="APPOINTMENT_RESCHEDULED",
            resource="appointments",
            user_id=user.id,
            details={
                "old_appointment_id": appointment.id,
                "new_appointment_id": new_appointment.id,
                "new_start_time": new_start_time.isoformat(),
            },
            ip_address=client_ip,
        )

        # Async side-effects
        if notif:
            enqueue_task("SEND_EMAIL_NOTIFICATION", {"notification_id": notif.id})
        enqueue_task("UPDATE_CALENDAR_EVENT", {"appointment_id": appointment.id})

        return _format_appointment_response(new_appointment)


def complete_appointment(
    db: Session,
    appointment_id: int,
    user: User,
    client_ip: Optional[str] = None,
) -> AppointmentResponse:
    """Transition: CONFIRMED -> COMPLETED."""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    if user.role == UserRole.DOCTOR:
        if not user.doctor or appointment.doctor_id != user.doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only complete visits assigned to you",
            )
    elif user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Insufficient privileges",
        )

    if appointment.status != AppointmentStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete appointment with status '{appointment.status.value}'. Must be CONFIRMED.",
        )

    appointment.status = AppointmentStatus.COMPLETED
    db.commit()
    db.refresh(appointment)

    log_audit(
        db=db,
        action="APPOINTMENT_COMPLETED",
        resource="appointments",
        user_id=user.id,
        details={"appointment_id": appointment.id},
        ip_address=client_ip,
    )

    return _format_appointment_response(appointment)


def no_show_appointment(
    db: Session,
    appointment_id: int,
    user: User,
    client_ip: Optional[str] = None,
) -> AppointmentResponse:
    """Transition: CONFIRMED -> NO_SHOW."""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    if user.role == UserRole.DOCTOR:
        if not user.doctor or appointment.doctor_id != user.doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only mark no-show on visits assigned to you",
            )
    elif user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Insufficient privileges",
        )

    if appointment.status != AppointmentStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot mark appointment as NO_SHOW with status '{appointment.status.value}'.",
        )

    appointment.status = AppointmentStatus.NO_SHOW
    db.commit()
    db.refresh(appointment)

    log_audit(
        db=db,
        action="APPOINTMENT_NO_SHOW",
        resource="appointments",
        user_id=user.id,
        details={"appointment_id": appointment.id},
        ip_address=client_ip,
    )

    return _format_appointment_response(appointment)


def _format_appointment_response(appointment: Appointment) -> AppointmentResponse:
    doctor_name = appointment.doctor.user.name if appointment.doctor and appointment.doctor.user else None
    specialization = appointment.doctor.specialization if appointment.doctor else None
    patient_name = appointment.patient.user.name if appointment.patient and appointment.patient.user else None

    return AppointmentResponse(
        id=appointment.id,
        patient_id=appointment.patient_id,
        doctor_id=appointment.doctor_id,
        start_time=ensure_utc(appointment.start_time),
        end_time=ensure_utc(appointment.end_time),
        status=appointment.status,
        hold_expires_at=ensure_utc(appointment.hold_expires_at),
        cancellation_reason=appointment.cancellation_reason,
        cancelled_by_user_id=appointment.cancelled_by_user_id,
        cancelled_at=ensure_utc(appointment.cancelled_at),
        rescheduled_from_id=appointment.rescheduled_from_id,
        doctor_name=doctor_name,
        doctor_specialization=specialization,
        patient_name=patient_name,
        created_at=ensure_utc(appointment.created_at),
        updated_at=ensure_utc(appointment.updated_at),
    )
