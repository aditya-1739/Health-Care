from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import Doctor, DoctorLeave, DoctorWorkingHours, LeaveStatus
from app.schemas.appointment import DoctorAvailabilityResponse, SlotResponse


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is timezone-aware in UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def calculate_doctor_availability(
    db: Session,
    doctor_id: int,
    target_date: date,
) -> DoctorAvailabilityResponse:
    """
    Calculate dynamic slot availability on the backend.
    
    Factors considered:
    1. Doctor existence and active status.
    2. Configured working hours for the target day of week.
    3. Doctor APPROVED leaves covering the target date (PENDING/DECLINED/CANCELLED do not block).
    4. Existing active appointments (CONFIRMED or unexpired HELD).
    5. Exclusion of past slots (slots prior to current UTC timestamp).
    """
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        )

    doctor_name = doctor.user.name if doctor.user else f"Doctor #{doctor.id}"
    slot_duration_mins = doctor.slot_duration or 30

    # If doctor is inactive, return no available slots
    if not doctor.active:
        return DoctorAvailabilityResponse(
            doctor_id=doctor.id,
            doctor_name=doctor_name,
            date=target_date,
            slot_duration=slot_duration_mins,
            total_slots=0,
            available_slots_count=0,
            slots=[],
        )

    # Check for APPROVED doctor leave on target date
    on_leave = (
        db.query(DoctorLeave)
        .filter(
            DoctorLeave.doctor_id == doctor.id,
            DoctorLeave.status == LeaveStatus.APPROVED,
            DoctorLeave.start_date <= target_date,
            DoctorLeave.end_date >= target_date,
        )
        .first()
    )
    if on_leave:
        return DoctorAvailabilityResponse(
            doctor_id=doctor.id,
            doctor_name=doctor_name,
            date=target_date,
            slot_duration=slot_duration_mins,
            total_slots=0,
            available_slots_count=0,
            slots=[],
        )

    # Get working hours for the day of week (Python date.weekday(): 0=Mon ... 6=Sun)
    day_of_week = target_date.weekday()
    working_hours_list = (
        db.query(DoctorWorkingHours)
        .filter(
            DoctorWorkingHours.doctor_id == doctor.id,
            DoctorWorkingHours.day_of_week == day_of_week,
        )
        .all()
    )

    if not working_hours_list:
        return DoctorAvailabilityResponse(
            doctor_id=doctor.id,
            doctor_name=doctor_name,
            date=target_date,
            slot_duration=slot_duration_mins,
            total_slots=0,
            available_slots_count=0,
            slots=[],
        )

    now_utc = datetime.now(timezone.utc)

    # Query all candidate appointments for this doctor
    all_appointments = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor.id,
            Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.HELD]),
        )
        .all()
    )

    generated_slots: List[SlotResponse] = []

    for wh in working_hours_list:
        # Convert start/end time into datetime for the day
        current_dt = datetime.combine(target_date, wh.start_time).replace(tzinfo=timezone.utc)
        shift_end_dt = datetime.combine(target_date, wh.end_time).replace(tzinfo=timezone.utc)
        slot_delta = timedelta(minutes=slot_duration_mins)

        while current_dt + slot_delta <= shift_end_dt:
            slot_start = current_dt
            slot_end = current_dt + slot_delta

            # Check if occupied by any active appointment
            is_occupied = False
            for app in all_appointments:
                app_start = ensure_utc(app.start_time)
                app_end = ensure_utc(app.end_time)
                if app_start < slot_end and app_end > slot_start:
                    if app.status == AppointmentStatus.CONFIRMED:
                        is_occupied = True
                        break
                    elif app.status == AppointmentStatus.HELD:
                        hold_exp = ensure_utc(app.hold_expires_at)
                        if hold_exp and hold_exp > now_utc:
                            is_occupied = True
                            break

            # Check if in the past
            is_past = slot_start < now_utc

            is_available = not is_occupied and not is_past

            generated_slots.append(
                SlotResponse(
                    start_time=slot_start,
                    end_time=slot_end,
                    available=is_available,
                )
            )

            current_dt += slot_delta

    # Sort slots chronologically
    generated_slots.sort(key=lambda s: s.start_time)
    available_count = sum(1 for s in generated_slots if s.available)

    return DoctorAvailabilityResponse(
        doctor_id=doctor.id,
        doctor_name=doctor_name,
        date=target_date,
        slot_duration=slot_duration_mins,
        total_slots=len(generated_slots),
        available_slots_count=available_count,
        slots=generated_slots,
    )
