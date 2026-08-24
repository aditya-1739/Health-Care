from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.deps import log_audit, require_admin
from app.core.security import get_password_hash
from app.models.appointment import Appointment, AppointmentStatus
from app.models.records import (
    AIJobStatus,
    AISummary,
    AuditLog,
    CalendarEvent,
    CalendarSyncStatus,
    MedicationReminder,
    Notification,
    NotificationStatus,
    ReminderStatus,
)
from app.models.user import Doctor, DoctorLeave, DoctorWorkingHours, LeaveStatus, Patient, PatientMedicalProfile, User, UserRole
from app.schemas.profile import (
    AdminUserDetailResponse,
    AppointmentHistoryItem,
    MedicalProfileResponse,
    UserProfileResponse,
    calculate_age,
)
from app.schemas.admin import (
    AdminDashboardStats,
    AdminLeaveRequestResponse,
    AdminLeaveReviewRequest,
    AdminPatientResponse,
    AuditLogResponse,
)
from app.schemas.doctor import (
    DoctorLeaveCreate,
    DoctorLeaveResponse,
    DoctorLeaveWithConflictsResponse,
    DoctorStatusUpdate,
    DoctorUpdateAdmin,
    WorkingHoursCreate,
    WorkingHoursResponse,
)
from app.schemas.notification import ReliabilityMetricsResponse
from app.schemas.user import UserCreateAdmin, UserResponse
from app.services.ai_service import AIService
from app.services.background_tasks import enqueue_task
from app.services.booking import _format_appointment_response
from app.services.calendar_service import CalendarService
from app.services.email_service import EmailService

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin provisions Doctor or Admin accounts",
)
def admin_create_user(
    payload: UserCreateAdmin,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Administrator endpoint to provision staff accounts (DOCTOR, ADMIN)."""
    existing_user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    new_user = User(
        name=payload.name.strip(),
        email=payload.email.lower().strip(),
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        status="active",
    )
    db.add(new_user)
    db.flush()

    doctor_id = None
    patient_id = None

    if payload.role == UserRole.DOCTOR:
        if not payload.specialization:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Specialization is required when creating a Doctor account",
            )
        doctor = Doctor(
            user_id=new_user.id,
            specialization=payload.specialization,
            bio=payload.bio,
            slot_duration=payload.slot_duration or 30,
            active=True,
        )
        db.add(doctor)
        db.flush()
        doctor_id = doctor.id
    elif payload.role == UserRole.PATIENT:
        patient = Patient(user_id=new_user.id)
        db.add(patient)
        db.flush()
        patient_id = patient.id

    db.commit()
    db.refresh(new_user)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="ADMIN_CREATE_USER",
        resource="users",
        user_id=current_user.id,
        details={"created_user_id": new_user.id, "created_email": new_user.email, "role": new_user.role.value},
        ip_address=client_ip,
    )

    return UserResponse(
        id=new_user.id,
        name=new_user.name,
        email=new_user.email,
        role=new_user.role,
        status=new_user.status,
        created_at=new_user.created_at,
        patient_id=patient_id,
        doctor_id=doctor_id,
    )


@router.put(
    "/doctors/{doctor_id}",
    response_model=UserResponse,
    summary="Admin updates doctor profile settings",
)
def admin_update_doctor(
    doctor_id: int,
    payload: DoctorUpdateAdmin,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update doctor specialization, bio, slot duration, and active status."""
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    if payload.specialization is not None:
        doctor.specialization = payload.specialization
    if payload.bio is not None:
        doctor.bio = payload.bio
    if payload.slot_duration is not None:
        doctor.slot_duration = payload.slot_duration
    if payload.active is not None:
        doctor.active = payload.active

    db.commit()
    db.refresh(doctor.user)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="ADMIN_UPDATE_DOCTOR",
        resource="doctors",
        user_id=current_user.id,
        details={"doctor_id": doctor.id, "updates": payload.model_dump(exclude_unset=True)},
        ip_address=client_ip,
    )

    return UserResponse(
        id=doctor.user.id,
        name=doctor.user.name,
        email=doctor.user.email,
        role=doctor.user.role,
        status=doctor.user.status,
        created_at=doctor.user.created_at,
        doctor_id=doctor.id,
    )


@router.patch(
    "/doctors/{doctor_id}/status",
    summary="Admin activates or deactivates a doctor",
)
def admin_toggle_doctor_status(
    doctor_id: int,
    payload: DoctorStatusUpdate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Toggle doctor active/inactive status."""
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    doctor.active = payload.active
    db.commit()

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="ADMIN_TOGGLE_DOCTOR_STATUS",
        resource="doctors",
        user_id=current_user.id,
        details={"doctor_id": doctor.id, "active": payload.active},
        ip_address=client_ip,
    )

    return {"message": f"Doctor status updated to {'active' if payload.active else 'inactive'}", "active": doctor.active}


@router.post(
    "/doctors/{doctor_id}/working-hours",
    response_model=WorkingHoursResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin configures doctor working hours",
)
def admin_add_working_hours(
    doctor_id: int,
    payload: WorkingHoursCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin configures doctor shifts."""
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    if payload.start_time >= payload.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time must be earlier than end_time",
        )

    wh = DoctorWorkingHours(
        doctor_id=doctor.id,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )
    db.add(wh)
    db.commit()
    db.refresh(wh)

    return WorkingHoursResponse(
        id=wh.id,
        day_of_week=wh.day_of_week,
        start_time=wh.start_time,
        end_time=wh.end_time,
    )


@router.post(
    "/doctors/{doctor_id}/leaves",
    response_model=DoctorLeaveWithConflictsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Admin adds leave for doctor and checks for conflicting appointments",
)
def admin_add_doctor_leave(
    doctor_id: int,
    payload: DoctorLeaveCreate,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin assigns leave to doctor and returns affected patient bookings."""
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    if payload.start_date > payload.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be later than end_date",
        )

    leave = DoctorLeave(
        doctor_id=doctor.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason,
    )
    db.add(leave)
    db.flush()

    day_start = datetime.combine(payload.start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    day_end = datetime.combine(payload.end_date + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)

    affected = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor.id,
            Appointment.start_time < day_end,
            Appointment.end_time > day_start,
            Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.HELD]),
        )
        .all()
    )

    db.commit()
    db.refresh(leave)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="ADMIN_SCHEDULED_DOCTOR_LEAVE",
        resource="doctor_leaves",
        user_id=current_user.id,
        details={
            "doctor_id": doctor.id,
            "start_date": str(payload.start_date),
            "end_date": str(payload.end_date),
            "affected_count": len(affected),
        },
        ip_address=client_ip,
    )

    return DoctorLeaveWithConflictsResponse(
        leave=DoctorLeaveResponse(
            id=leave.id,
            doctor_id=leave.doctor_id,
            start_date=leave.start_date,
            end_date=leave.end_date,
            reason=leave.reason,
        ),
        affected_appointments=[_format_appointment_response(a) for a in affected],
    )


@router.delete(
    "/doctors/{doctor_id}/leaves/{leave_id}",
    summary="Admin deletes a doctor leave record",
)
def admin_delete_doctor_leave(
    doctor_id: int,
    leave_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin removes doctor leave."""
    leave = (
        db.query(DoctorLeave)
        .filter(DoctorLeave.id == leave_id, DoctorLeave.doctor_id == doctor_id)
        .first()
    )
    if not leave:
        raise HTTPException(status_code=404, detail="Leave record not found")

    db.delete(leave)
    db.commit()
    return {"message": "Leave record deleted successfully"}


# -----------------------------------------------------------------------------
# Phase 3: Reliability Engine & Operational Recovery Controls
# -----------------------------------------------------------------------------

@router.get(
    "/reliability/metrics",
    response_model=ReliabilityMetricsResponse,
    summary="Admin operational metrics for AI, notifications, calendar, and reminders",
)
def get_reliability_metrics(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get system health metrics for asynchronous background queues."""
    ai_metrics = {
        "PENDING": db.query(AISummary).filter(AISummary.status == AIJobStatus.PENDING).count(),
        "PROCESSING": db.query(AISummary).filter(AISummary.status == AIJobStatus.PROCESSING).count(),
        "COMPLETED": db.query(AISummary).filter(AISummary.status == AIJobStatus.COMPLETED).count(),
        "FAILED": db.query(AISummary).filter(AISummary.status == AIJobStatus.FAILED).count(),
    }

    notif_metrics = {
        "QUEUED": db.query(Notification).filter(Notification.status == NotificationStatus.QUEUED).count(),
        "SENT": db.query(Notification).filter(Notification.status == NotificationStatus.SENT).count(),
        "FAILED": db.query(Notification).filter(Notification.status == NotificationStatus.FAILED).count(),
    }

    med_metrics = {
        "PENDING": db.query(MedicationReminder).filter(MedicationReminder.status == ReminderStatus.PENDING).count(),
        "SENT": db.query(MedicationReminder).filter(MedicationReminder.status == ReminderStatus.SENT).count(),
        "FAILED": db.query(MedicationReminder).filter(MedicationReminder.status == ReminderStatus.FAILED).count(),
    }

    cal_metrics = {
        "SYNCED": db.query(CalendarEvent).filter(CalendarEvent.sync_status == CalendarSyncStatus.SYNCED).count(),
        "PENDING": db.query(CalendarEvent).filter(CalendarEvent.sync_status == CalendarSyncStatus.PENDING).count(),
        "FAILED": db.query(CalendarEvent).filter(CalendarEvent.sync_status == CalendarSyncStatus.FAILED).count(),
    }

    return ReliabilityMetricsResponse(
        ai_jobs=ai_metrics,
        notifications=notif_metrics,
        medication_reminders=med_metrics,
        calendar_syncs=cal_metrics,
    )


@router.post(
    "/reliability/retry-ai/{summary_id}",
    summary="Admin manually triggers retry of a failed AI summary job",
)
def retry_failed_ai_job(
    summary_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manually re-run failed AI Pre-Visit or Post-Visit summary."""
    summary = db.query(AISummary).filter(AISummary.id == summary_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="AI Summary record not found")

    if summary.summary_type == "PRE_VISIT":
        res = AIService.generate_previsit_summary(db, summary.appointment_id)
    else:
        res = AIService.generate_postvisit_summary(db, summary.appointment_id)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="ADMIN_RETRY_AI_JOB",
        resource="ai_summaries",
        user_id=current_user.id,
        details={"summary_id": summary_id, "status": res.status.value},
        ip_address=client_ip,
    )

    return {"message": "AI job retried", "status": res.status.value}


@router.post(
    "/reliability/retry-notification/{notification_id}",
    summary="Admin manually retries a failed email notification",
)
def retry_failed_notification(
    notification_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manually re-dispatch failed notification."""
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification record not found")

    res = EmailService.process_notification(db, notification_id)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="ADMIN_RETRY_NOTIFICATION",
        resource="notifications",
        user_id=current_user.id,
        details={"notification_id": notification_id, "status": res.status.value if res else None},
        ip_address=client_ip,
    )

    return {"message": "Notification retried", "status": res.status.value if res else None}


@router.post(
    "/reliability/retry-calendar/{event_id}",
    summary="Admin manually retries a failed calendar synchronization",
)
def retry_failed_calendar_sync(
    event_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Manually re-sync calendar event."""
    cal_event = db.query(CalendarEvent).filter(CalendarEvent.id == event_id).first()
    if not cal_event:
        raise HTTPException(status_code=404, detail="Calendar Event record not found")

    res = CalendarService.sync_confirmed_appointment(db, cal_event.appointment_id)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="ADMIN_RETRY_CALENDAR_SYNC",
        resource="calendar_events",
        user_id=current_user.id,
        details={"calendar_event_id": event_id},
        ip_address=client_ip,
    )

    return {"message": "Calendar sync retried"}


@router.get(
    "/dashboard",
    response_model=AdminDashboardStats,
    summary="Admin system dashboard metrics",
)
def get_admin_dashboard(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Retrieve high-level system usage counts."""
    total_users = db.query(User).count()
    total_patients = db.query(Patient).count()
    total_doctors = db.query(Doctor).count()
    active_doctors = db.query(Doctor).filter(Doctor.active == True).count()
    total_appointments = db.query(Appointment).count()

    return AdminDashboardStats(
        total_users=total_users,
        total_patients=total_patients,
        total_doctors=total_doctors,
        active_doctors=active_doctors,
        total_appointments=total_appointments,
    )


@router.get(
    "/audit-logs",
    response_model=List[AuditLogResponse],
    summary="List recent security & system audit logs",
)
def get_audit_logs(
    limit: int = 100,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Inspect system actions and audit logs."""
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return logs


@router.get(
    "/patients",
    response_model=List[AdminPatientResponse],
    summary="Admin retrieves all registered patients",
)
def get_admin_patients(
    search: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin endpoint to search and view registered patients."""
    query = db.query(Patient).join(User, Patient.user_id == User.id)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            (User.name.ilike(s)) | (User.email.ilike(s)) | (Patient.phone.ilike(s))
        )
    patients = query.order_by(Patient.created_at.desc()).all()

    results = []
    for p in patients:
        app_count = db.query(Appointment).filter(Appointment.patient_id == p.id).count()
        results.append(
            AdminPatientResponse(
                id=p.id,
                user_id=p.user_id,
                name=p.user.name if p.user else "Unknown",
                email=p.user.email if p.user else "Unknown",
                phone=p.phone,
                status=p.user.status if p.user else "active",
                created_at=p.created_at,
                appointments_count=app_count,
            )
        )
    return results


@router.get(
    "/leave-requests",
    response_model=List[AdminLeaveRequestResponse],
    summary="Admin reviews all doctor leave requests",
)
def get_admin_leave_requests(
    status: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List doctor leave requests with affected appointments count."""
    query = db.query(DoctorLeave)
    if status:
        query = query.filter(DoctorLeave.status == status)

    # Sort PENDING first, then by requested_at descending
    from sqlalchemy import case
    order_clause = case((DoctorLeave.status == LeaveStatus.PENDING, 0), else_=1)
    leaves = query.order_by(order_clause, DoctorLeave.requested_at.desc()).all()

    results = []
    for l in leaves:
        doctor = l.doctor
        doc_user = doctor.user if doctor else None
        day_start = datetime.combine(l.start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        day_end = datetime.combine(l.end_date + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)

        affected = (
            db.query(Appointment)
            .filter(
                Appointment.doctor_id == l.doctor_id,
                Appointment.start_time < day_end,
                Appointment.end_time > day_start,
                Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.HELD]),
            )
            .all()
        )

        results.append(
            AdminLeaveRequestResponse(
                id=l.id,
                doctor_id=l.doctor_id,
                doctor_name=doc_user.name if doc_user else f"Doctor #{l.doctor_id}",
                doctor_specialization=doctor.specialization if doctor else "General",
                doctor_email=doc_user.email if doc_user else "",
                start_date=l.start_date,
                end_date=l.end_date,
                reason=l.reason,
                status=l.status,
                requested_at=l.requested_at,
                reviewed_at=l.reviewed_at,
                reviewed_by_user_id=l.reviewed_by_user_id,
                admin_remarks=l.admin_remarks,
                affected_appointments_count=len(affected),
                affected_appointments=[_format_appointment_response(a) for a in affected],
            )
        )
    return results


@router.post(
    "/leave-requests/{leave_id}/approve",
    response_model=AdminLeaveRequestResponse,
    summary="Admin approves doctor leave request",
)
def approve_leave_request(
    leave_id: int,
    payload: Optional[AdminLeaveReviewRequest] = None,
    request: Request = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin approves pending doctor leave."""
    leave = db.query(DoctorLeave).filter(DoctorLeave.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")

    if leave.status != LeaveStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only PENDING leave requests can be approved. Current status: '{leave.status.value}'.",
        )

    remarks = payload.remarks.strip() if payload and payload.remarks else None
    leave.status = LeaveStatus.APPROVED
    leave.reviewed_at = datetime.now(timezone.utc)
    leave.reviewed_by_user_id = current_user.id
    leave.admin_remarks = remarks

    # Query affected appointments
    day_start = datetime.combine(leave.start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    day_end = datetime.combine(leave.end_date + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc)
    affected = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == leave.doctor_id,
            Appointment.start_time < day_end,
            Appointment.end_time > day_start,
            Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.HELD]),
        )
        .all()
    )

    # Outbox: Notify doctor of approval
    doctor = leave.doctor
    doc_user = doctor.user if doctor else None
    if doc_user:
        notif = EmailService.queue_notification(
            db=db,
            user_id=doc_user.id,
            recipient_email=doc_user.email,
            event_type="LEAVE_APPROVED",
            subject="Doctor Leave Request Approved",
            body_html=(
                f"<p>Dear {doc_user.name},</p>"
                f"<p>Your leave request from <strong>{leave.start_date} to {leave.end_date}</strong> has been <strong>APPROVED</strong> by administrator.</p>"
                f"<p><strong>Remarks:</strong> {remarks or 'Approved as requested.'}</p>"
            ),
            idempotency_key=f"notif_leave_{leave.id}_APPROVED",
        )
        if notif:
            enqueue_task("SEND_EMAIL_NOTIFICATION", {"notification_id": notif.id})

    db.commit()
    db.refresh(leave)

    client_ip = request.client.host if request and request.client else None
    log_audit(
        db=db,
        action="LEAVE_APPROVED",
        resource="doctor_leaves",
        user_id=current_user.id,
        details={
            "leave_id": leave.id,
            "doctor_id": leave.doctor_id,
            "remarks": remarks,
            "affected_count": len(affected),
        },
        ip_address=client_ip,
    )

    return AdminLeaveRequestResponse(
        id=leave.id,
        doctor_id=leave.doctor_id,
        doctor_name=doc_user.name if doc_user else f"Doctor #{leave.doctor_id}",
        doctor_specialization=doctor.specialization if doctor else "General",
        doctor_email=doc_user.email if doc_user else "",
        start_date=leave.start_date,
        end_date=leave.end_date,
        reason=leave.reason,
        status=leave.status,
        requested_at=leave.requested_at,
        reviewed_at=leave.reviewed_at,
        reviewed_by_user_id=leave.reviewed_by_user_id,
        admin_remarks=leave.admin_remarks,
        affected_appointments_count=len(affected),
        affected_appointments=[_format_appointment_response(a) for a in affected],
    )


@router.post(
    "/leave-requests/{leave_id}/decline",
    response_model=AdminLeaveRequestResponse,
    summary="Admin declines doctor leave request with mandatory remarks",
)
def decline_leave_request(
    leave_id: int,
    payload: AdminLeaveReviewRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin declines pending doctor leave request."""
    if not payload or not payload.remarks or not payload.remarks.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Remarks are required when declining a leave request.",
        )

    leave = db.query(DoctorLeave).filter(DoctorLeave.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")

    if leave.status != LeaveStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only PENDING leave requests can be declined. Current status: '{leave.status.value}'.",
        )

    remarks = payload.remarks.strip()
    leave.status = LeaveStatus.DECLINED
    leave.reviewed_at = datetime.now(timezone.utc)
    leave.reviewed_by_user_id = current_user.id
    leave.admin_remarks = remarks

    # Outbox: Notify doctor of decline
    doctor = leave.doctor
    doc_user = doctor.user if doctor else None
    if doc_user:
        notif = EmailService.queue_notification(
            db=db,
            user_id=doc_user.id,
            recipient_email=doc_user.email,
            event_type="LEAVE_DECLINED",
            subject="Doctor Leave Request Declined",
            body_html=(
                f"<p>Dear {doc_user.name},</p>"
                f"<p>Your leave request from <strong>{leave.start_date} to {leave.end_date}</strong> was <strong>DECLINED</strong> by administrator.</p>"
                f"<p><strong>Reason/Remarks:</strong> {remarks}</p>"
            ),
            idempotency_key=f"notif_leave_{leave.id}_DECLINED",
        )
        if notif:
            enqueue_task("SEND_EMAIL_NOTIFICATION", {"notification_id": notif.id})

    db.commit()
    db.refresh(leave)

    client_ip = request.client.host if request and request.client else None
    log_audit(
        db=db,
        action="LEAVE_DECLINED",
        resource="doctor_leaves",
        user_id=current_user.id,
        details={
            "leave_id": leave.id,
            "doctor_id": leave.doctor_id,
            "remarks": remarks,
        },
        ip_address=client_ip,
    )

    return AdminLeaveRequestResponse(
        id=leave.id,
        doctor_id=leave.doctor_id,
        doctor_name=doc_user.name if doc_user else f"Doctor #{leave.doctor_id}",
        doctor_specialization=doctor.specialization if doctor else "General",
        doctor_email=doc_user.email if doc_user else "",
        start_date=leave.start_date,
        end_date=leave.end_date,
        reason=leave.reason,
        status=leave.status,
        requested_at=leave.requested_at,
        reviewed_at=leave.reviewed_at,
        reviewed_by_user_id=leave.reviewed_by_user_id,
        admin_remarks=leave.admin_remarks,
        affected_appointments_count=0,
        affected_appointments=[],
    )


@router.get(
    "/users",
    response_model=List[UserResponse],
    summary="Admin searches and lists system users",
)
def admin_list_users(
    search: Optional[str] = None,
    role: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin endpoint to search, filter by role, and list users."""
    query = db.query(User).options(joinedload(User.patient), joinedload(User.doctor))

    if role and role.upper() != "ALL":
        try:
            target_role = UserRole(role.upper())
            query = query.filter(User.role == target_role)
        except ValueError:
            pass

    if search and search.strip():
        s = f"%{search.strip()}%"
        query = query.filter(
            (User.name.ilike(s)) | (User.email.ilike(s)) | (User.phone.ilike(s))
        )

    users = query.order_by(User.created_at.desc()).offset(offset).limit(limit).all()

    results = []
    for u in users:
        results.append(
            UserResponse(
                id=u.id,
                name=u.name,
                email=u.email,
                role=u.role,
                status=u.status,
                created_at=u.created_at,
                patient_id=u.patient.id if u.patient else None,
                doctor_id=u.doctor.id if u.doctor else None,
            )
        )
    return results


@router.get(
    "/users/{user_id}/profile",
    response_model=AdminUserDetailResponse,
    summary="Admin views complete profile for any user",
)
def admin_get_user_profile(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin inspects basic info, medical profile (if patient), or doctor details."""
    user = (
        db.query(User)
        .options(
            joinedload(User.patient).joinedload(Patient.medical_profile),
            joinedload(User.doctor).joinedload(Doctor.working_hours),
            joinedload(User.doctor).joinedload(Doctor.leaves),
        )
        .filter(User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    phone = user.phone
    dob = user.date_of_birth
    gender = None
    address = None
    emergency_contact_name = None
    emergency_contact_phone = None
    specialization = None
    bio = None
    slot_duration = None
    active = None
    med_profile_resp = None
    patient_dict = None
    doctor_dict = None

    if user.patient:
        p = user.patient
        phone = p.phone or phone
        dob = p.date_of_birth or dob
        gender = p.gender
        address = p.address
        emergency_contact_name = p.emergency_contact_name
        emergency_contact_phone = p.emergency_contact_phone
        patient_dict = {
            "id": p.id,
            "phone": p.phone,
            "date_of_birth": str(p.date_of_birth) if p.date_of_birth else None,
            "gender": p.gender,
            "address": p.address,
            "emergency_contact_name": p.emergency_contact_name,
            "emergency_contact_phone": p.emergency_contact_phone,
        }
        if p.medical_profile:
            mp = p.medical_profile
            med_profile_resp = MedicalProfileResponse(
                id=mp.id,
                patient_id=p.id,
                blood_group=mp.blood_group,
                height_cm=mp.height_cm,
                weight_kg=mp.weight_kg,
                allergies=mp.allergies,
                chronic_conditions=mp.chronic_conditions,
                current_medications=mp.current_medications,
                past_surgeries=mp.past_surgeries,
                family_history=mp.family_history,
                medical_notes=mp.medical_notes,
                created_at=mp.created_at,
                updated_at=mp.updated_at,
            )

    if user.doctor:
        d = user.doctor
        phone = d.phone or phone
        dob = d.date_of_birth or dob
        specialization = d.specialization
        bio = d.bio
        slot_duration = d.slot_duration
        active = d.active
        doctor_dict = {
            "id": d.id,
            "specialization": d.specialization,
            "bio": d.bio,
            "slot_duration": d.slot_duration,
            "active": d.active,
            "working_hours_count": len(d.working_hours),
            "leaves_count": len(d.leaves),
        }

    age = calculate_age(dob)

    profile_resp = UserProfileResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        status=user.status,
        phone=phone,
        date_of_birth=dob,
        age=age,
        gender=gender,
        address=address,
        emergency_contact_name=emergency_contact_name,
        emergency_contact_phone=emergency_contact_phone,
        specialization=specialization,
        bio=bio,
        slot_duration=slot_duration,
        active=active,
        patient_id=user.patient.id if user.patient else None,
        doctor_id=user.doctor.id if user.doctor else None,
        created_at=user.created_at,
    )

    # Fetch appointments
    appt_query = (
        db.query(Appointment)
        .options(
            joinedload(Appointment.doctor).joinedload(Doctor.user),
            joinedload(Appointment.patient).joinedload(Patient.user),
            joinedload(Appointment.symptom_form),
            joinedload(Appointment.prescription),
        )
    )
    if user.patient:
        appt_query = appt_query.filter(Appointment.patient_id == user.patient.id)
    elif user.doctor:
        appt_query = appt_query.filter(Appointment.doctor_id == user.doctor.id)
    else:
        appt_query = None

    appointments_list = []
    appts_count = 0
    if appt_query:
        appts = appt_query.order_by(Appointment.start_time.desc()).limit(20).all()
        appts_count = len(appts)
        for a in appts:
            doc_user = a.doctor.user if a.doctor else None
            pat_user = a.patient.user if a.patient else None
            appointments_list.append(
                AppointmentHistoryItem(
                    id=a.id,
                    doctor_id=a.doctor_id,
                    doctor_name=doc_user.name if doc_user else f"Doctor #{a.doctor_id}",
                    doctor_specialization=a.doctor.specialization if a.doctor else "General",
                    patient_id=a.patient_id,
                    patient_name=pat_user.name if pat_user else f"Patient #{a.patient_id}",
                    start_time=a.start_time,
                    end_time=a.end_time,
                    status=a.status.value,
                    cancellation_reason=a.cancellation_reason,
                    decline_remarks=a.decline_remarks,
                    chief_complaint=a.symptom_form.chief_complaint if a.symptom_form else None,
                    has_prescription=a.prescription is not None,
                    created_at=a.created_at,
                )
            )

    return AdminUserDetailResponse(
        user=profile_resp,
        patient=patient_dict,
        medical_profile=med_profile_resp,
        doctor=doctor_dict,
        appointments_count=appts_count,
        recent_appointments=appointments_list,
    )

