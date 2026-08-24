from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.deps import log_audit, require_doctor
from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import Doctor, DoctorLeave, DoctorWorkingHours, LeaveStatus, User
from app.schemas.appointment import DoctorAvailabilityResponse
from app.schemas.doctor import (
    DoctorLeaveCreate,
    DoctorLeaveResponse,
    DoctorLeaveWithConflictsResponse,
    DoctorPublicResponse,
    WorkingHoursCreate,
    WorkingHoursResponse,
)
from app.services.availability import calculate_doctor_availability
from app.services.booking import _format_appointment_response

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.get(
    "",
    response_model=List[DoctorPublicResponse],
    summary="List all active doctors with public profile details",
)
def list_doctors(
    specialization: Optional[str] = Query(None, description="Filter by doctor specialization"),
    db: Session = Depends(get_db),
):
    """Exposes safe public profile information."""
    query = (
        db.query(Doctor)
        .join(User)
        .options(joinedload(Doctor.user), joinedload(Doctor.working_hours))
        .filter(Doctor.active == True, User.status == "active")
    )

    if specialization:
        query = query.filter(Doctor.specialization.ilike(f"%{specialization}%"))

    doctors = query.all()
    results = []
    for doc in doctors:
        results.append(
            DoctorPublicResponse(
                id=doc.id,
                user_id=doc.user_id,
                name=doc.user.name,
                email=doc.user.email,
                specialization=doc.specialization,
                bio=doc.bio,
                slot_duration=doc.slot_duration,
                active=doc.active,
                profile_image_url=doc.user.profile_image_url,
                working_hours=[
                    WorkingHoursResponse(
                        id=wh.id,
                        day_of_week=wh.day_of_week,
                        start_time=wh.start_time,
                        end_time=wh.end_time,
                    )
                    for wh in doc.working_hours
                ],
            )
        )
    return results


@router.get(
    "/{doctor_id}",
    response_model=DoctorPublicResponse,
    summary="Get single doctor public profile",
)
def get_doctor_by_id(
    doctor_id: int,
    db: Session = Depends(get_db),
):
    """Retrieve public profile and working hours for a specific doctor."""
    doctor = (
        db.query(Doctor)
        .options(joinedload(Doctor.user), joinedload(Doctor.working_hours))
        .filter(Doctor.id == doctor_id)
        .first()
    )
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    return DoctorPublicResponse(
        id=doctor.id,
        user_id=doctor.user_id,
        name=doctor.user.name,
        email=doctor.user.email,
        specialization=doctor.specialization,
        bio=doctor.bio,
        slot_duration=doctor.slot_duration,
        active=doctor.active,
        profile_image_url=doctor.user.profile_image_url,
        working_hours=[
            WorkingHoursResponse(
                id=wh.id,
                day_of_week=wh.day_of_week,
                start_time=wh.start_time,
                end_time=wh.end_time,
            )
            for wh in doctor.working_hours
        ],
    )


@router.get(
    "/{doctor_id}/availability",
    response_model=DoctorAvailabilityResponse,
    summary="Get dynamic slot availability for doctor on a specific date",
)
def get_doctor_availability_endpoint(
    doctor_id: int,
    date_str: str = Query(..., alias="date", description="Date formatted as YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """Compute real-time available appointment slots on the backend."""
    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Please provide YYYY-MM-DD",
        )

    return calculate_doctor_availability(db, doctor_id, target_date)


@router.get(
    "/{doctor_id}/working-hours",
    response_model=List[WorkingHoursResponse],
    summary="Get doctor's configured working hours",
)
def get_doctor_working_hours(
    doctor_id: int,
    db: Session = Depends(get_db),
):
    """View shift and working hours for a doctor."""
    wh_list = (
        db.query(DoctorWorkingHours)
        .filter(DoctorWorkingHours.doctor_id == doctor_id)
        .order_by(DoctorWorkingHours.day_of_week.asc())
        .all()
    )
    return [
        WorkingHoursResponse(
            id=wh.id,
            day_of_week=wh.day_of_week,
            start_time=wh.start_time,
            end_time=wh.end_time,
        )
        for wh in wh_list
    ]


@router.post(
    "/me/working-hours",
    response_model=WorkingHoursResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Doctor configures their own working hours",
)
def add_my_working_hours(
    payload: WorkingHoursCreate,
    current_user: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    """Doctor adds a working shift."""
    doctor = current_user.doctor
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found",
        )

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


@router.get(
    "/me/leaves",
    response_model=List[DoctorLeaveResponse],
    summary="Doctor views their own leaves",
)
def list_my_leaves(
    current_user: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    """Doctor queries their leaves with approval status and admin remarks."""
    doctor = current_user.doctor
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    leaves = (
        db.query(DoctorLeave)
        .filter(DoctorLeave.doctor_id == doctor.id)
        .order_by(DoctorLeave.requested_at.desc())
        .all()
    )
    return [
        DoctorLeaveResponse(
            id=l.id,
            doctor_id=l.doctor_id,
            start_date=l.start_date,
            end_date=l.end_date,
            reason=l.reason,
            status=l.status,
            requested_at=l.requested_at,
            reviewed_at=l.reviewed_at,
            reviewed_by_user_id=l.reviewed_by_user_id,
            admin_remarks=l.admin_remarks,
        )
        for l in leaves
    ]


@router.post(
    "/me/leaves",
    response_model=DoctorLeaveWithConflictsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Doctor submits a leave request for administrator review",
)
def add_my_leave(
    payload: DoctorLeaveCreate,
    request: Request,
    current_user: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    """Doctor submits a leave request. Starts in PENDING status awaiting admin approval."""
    doctor = current_user.doctor
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    if payload.start_date > payload.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be later than end_date",
        )

    if payload.start_date < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot submit a leave request for past dates",
        )

    if not payload.reason or not payload.reason.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A reason must be provided for the leave request",
        )

    # Check for active overlapping pending or approved leave requests
    overlap = (
        db.query(DoctorLeave)
        .filter(
            DoctorLeave.doctor_id == doctor.id,
            DoctorLeave.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
            DoctorLeave.start_date <= payload.end_date,
            DoctorLeave.end_date >= payload.start_date,
        )
        .first()
    )
    if overlap:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An overlapping {overlap.status.value.lower()} leave request already exists for these dates ({overlap.start_date} to {overlap.end_date}).",
        )

    leave = DoctorLeave(
        doctor_id=doctor.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason.strip(),
        status=LeaveStatus.PENDING,
        requested_at=datetime.now(timezone.utc),
    )
    db.add(leave)
    db.flush()

    # Detect affected appointments between start_date 00:00 UTC and end_date 23:59 UTC
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
        action="LEAVE_REQUESTED",
        resource="doctor_leaves",
        user_id=current_user.id,
        details={
            "doctor_id": doctor.id,
            "leave_id": leave.id,
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
            status=leave.status,
            requested_at=leave.requested_at,
            reviewed_at=leave.reviewed_at,
            reviewed_by_user_id=leave.reviewed_by_user_id,
            admin_remarks=leave.admin_remarks,
        ),
        affected_appointments=[_format_appointment_response(a) for a in affected],
    )


@router.delete(
    "/me/leaves/{leave_id}",
    summary="Doctor cancels their own leave request",
)
def delete_my_leave(
    leave_id: int,
    request: Request,
    current_user: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    """Doctor cancels a leave request."""
    doctor = current_user.doctor
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")

    leave = (
        db.query(DoctorLeave)
        .filter(DoctorLeave.id == leave_id, DoctorLeave.doctor_id == doctor.id)
        .first()
    )
    if not leave:
        raise HTTPException(status_code=404, detail="Leave record not found")

    leave.status = LeaveStatus.CANCELLED
    db.commit()

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="LEAVE_CANCELLED",
        resource="doctor_leaves",
        user_id=current_user.id,
        details={"leave_id": leave.id, "doctor_id": doctor.id},
        ip_address=client_ip,
    )

    return {"message": "Leave request cancelled successfully"}
