from datetime import date, datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_admin, require_doctor, require_patient
from app.core.rate_limit import rate_limiter
from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import User, UserRole
from app.schemas.appointment import (
    AlternativeSlotsResponse,
    AppointmentCancelRequest,
    AppointmentConfirmRequest,
    AppointmentDeclineRequest,
    AppointmentHoldRequest,
    AppointmentHoldResponse,
    AppointmentRescheduleRequest,
    AppointmentResponse,
    DoctorAvailabilityResponse,
)
from app.services.alternatives import find_alternative_slots
from app.services.availability import calculate_doctor_availability
from app.services.booking import (
    _format_appointment_response,
    cancel_appointment,
    complete_appointment,
    confirm_appointment,
    decline_appointment,
    hold_slot,
    no_show_appointment,
    reschedule_appointment,
)
from app.services.idempotency import check_idempotency, store_idempotent_response

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.post(
    "/hold",
    response_model=AppointmentHoldResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter("appointment_hold", max_requests=settings.RATE_LIMIT_BOOKING_PER_MINUTE))],
    summary="Create temporary 5-minute slot hold for a patient",
)
def hold_appointment_slot(
    payload: AppointmentHoldRequest,
    request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """
    Temporarily holds an appointment slot for 5 minutes.
    Idempotency key can be passed via X-Idempotency-Key header or payload body.
    """
    idemp_key = x_idempotency_key or payload.idempotency_key
    cached = check_idempotency(db, current_user.id, "HOLD_APPOINTMENT", idemp_key, payload.model_dump())
    if cached:
        code, body = cached
        return AppointmentHoldResponse(**body)

    client_ip = request.client.host if request.client else None
    result = hold_slot(db, current_user, payload, client_ip=client_ip)

    if idemp_key:
        store_idempotent_response(
            db=db,
            user_id=current_user.id,
            action="HOLD_APPOINTMENT",
            idempotency_key=idemp_key,
            payload=payload.model_dump(),
            response_code=201,
            response_body=result.model_dump(),
        )

    return result


@router.post(
    "/{appointment_id}/confirm",
    response_model=AppointmentResponse,
    dependencies=[Depends(rate_limiter("appointment_confirm", max_requests=settings.RATE_LIMIT_BOOKING_PER_MINUTE))],
    summary="Confirm a previously held appointment within TTL",
)
def confirm_appointment_slot(
    appointment_id: int,
    payload: Optional[AppointmentConfirmRequest] = None,
    request: Request = None,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """Confirm a HELD appointment before the 5-minute hold expires."""
    idemp_key = x_idempotency_key or (payload.idempotency_key if payload else None)
    cached = check_idempotency(
        db, current_user.id, f"CONFIRM_APPOINTMENT_{appointment_id}", idemp_key, {"appointment_id": appointment_id}
    )
    if cached:
        code, body = cached
        return AppointmentResponse(**body)

    client_ip = request.client.host if request and request.client else None
    result = confirm_appointment(db, appointment_id, current_user, idempotency_key=idemp_key, client_ip=client_ip)

    if idemp_key:
        store_idempotent_response(
            db=db,
            user_id=current_user.id,
            action=f"CONFIRM_APPOINTMENT_{appointment_id}",
            idempotency_key=idemp_key,
            payload={"appointment_id": appointment_id},
            response_code=200,
            response_body=result.model_dump(),
        )

    return result


@router.get(
    "",
    response_model=List[AppointmentResponse],
    summary="List appointments for the calling user with pagination",
)
def list_appointments(
    status_filter: Optional[AppointmentStatus] = Query(None, alias="status"),
    timeframe: Optional[str] = Query(None, description="upcoming / past"),
    limit: int = Query(50, ge=1, le=100, description="Page limit (max 100)"),
    offset: int = Query(0, ge=0, description="Page offset"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List appointments with pagination and role-based data isolation:
    - PATIENT: only their appointments
    - DOCTOR: only their assigned appointments
    - ADMIN: all appointments
    """
    query = db.query(Appointment)

    if current_user.role == UserRole.PATIENT:
        if not current_user.patient:
            return []
        query = query.filter(Appointment.patient_id == current_user.patient.id)
    elif current_user.role == UserRole.DOCTOR:
        if not current_user.doctor:
            return []
        query = query.filter(Appointment.doctor_id == current_user.doctor.id)

    if status_filter:
        query = query.filter(Appointment.status == status_filter)

    now_utc = datetime.now(timezone.utc)
    if timeframe == "upcoming":
        query = query.filter(Appointment.start_time >= now_utc)
    elif timeframe == "past":
        query = query.filter(Appointment.start_time < now_utc)

    appointments = query.order_by(Appointment.start_time.asc()).offset(offset).limit(limit).all()
    return [_format_appointment_response(app) for app in appointments]


@router.get(
    "/{appointment_id}",
    response_model=AppointmentResponse,
    summary="Get single appointment details (Strictly isolated)",
)
def get_appointment_by_id(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Data isolation:
    - Patient can only access own appointment.
    - Doctor can only access assigned appointment.
    - Admin can access any appointment.
    """
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    if current_user.role == UserRole.PATIENT:
        if not current_user.patient or appointment.patient_id != current_user.patient.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot view another patient's appointment",
            )
    elif current_user.role == UserRole.DOCTOR:
        if not current_user.doctor or appointment.doctor_id != current_user.doctor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot view appointments assigned to another doctor",
            )

    return _format_appointment_response(appointment)


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentResponse,
    summary="Cancel appointment and release slot",
)
def cancel_appointment_endpoint(
    appointment_id: int,
    payload: Optional[AppointmentCancelRequest] = None,
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel an appointment."""
    client_ip = request.client.host if request and request.client else None
    reason = payload.reason if payload else None
    return cancel_appointment(db, appointment_id, current_user, reason=reason, client_ip=client_ip)


@router.post(
    "/{appointment_id}/decline",
    response_model=AppointmentResponse,
    summary="Doctor declines an assigned appointment with remarks",
)
def decline_appointment_endpoint(
    appointment_id: int,
    payload: AppointmentDeclineRequest,
    request: Request,
    current_user: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    """Doctor declines an assigned appointment."""
    client_ip = request.client.host if request.client else None
    return decline_appointment(db, appointment_id, current_user, remarks=payload.remarks, client_ip=client_ip)


@router.post(
    "/{appointment_id}/reschedule",
    response_model=AppointmentResponse,
    summary="Atomically reschedule appointment to a new slot",
)
def reschedule_appointment_endpoint(
    appointment_id: int,
    payload: AppointmentRescheduleRequest,
    request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reschedule an existing appointment to a new slot."""
    idemp_key = x_idempotency_key or payload.idempotency_key
    cached = check_idempotency(
        db, current_user.id, f"RESCHEDULE_{appointment_id}", idemp_key, payload.model_dump()
    )
    if cached:
        code, body = cached
        return AppointmentResponse(**body)

    client_ip = request.client.host if request.client else None
    result = reschedule_appointment(
        db,
        appointment_id,
        current_user,
        new_start_time=payload.new_start_time,
        idempotency_key=idemp_key,
        client_ip=client_ip,
    )

    if idemp_key:
        store_idempotent_response(
            db=db,
            user_id=current_user.id,
            action=f"RESCHEDULE_{appointment_id}",
            idempotency_key=idemp_key,
            payload=payload.model_dump(),
            response_code=200,
            response_body=result.model_dump(),
        )

    return result


@router.post(
    "/{appointment_id}/complete",
    response_model=AppointmentResponse,
    summary="Mark appointment visit as completed (Doctor/Admin)",
)
def complete_appointment_endpoint(
    appointment_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark consultation as completed."""
    client_ip = request.client.host if request.client else None
    return complete_appointment(db, appointment_id, current_user, client_ip=client_ip)


@router.post(
    "/{appointment_id}/no-show",
    response_model=AppointmentResponse,
    summary="Mark appointment as patient no-show (Doctor/Admin)",
)
def no_show_appointment_endpoint(
    appointment_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark appointment as patient no-show."""
    client_ip = request.client.host if request.client else None
    return no_show_appointment(db, appointment_id, current_user, client_ip=client_ip)


@router.get(
    "/{appointment_id}/alternative-slots",
    response_model=AlternativeSlotsResponse,
    summary="Suggest smart alternative slots for an appointment",
)
def get_alternative_slots_endpoint(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Find and rank alternative available slots for this doctor."""
    return find_alternative_slots(db, appointment_id)
