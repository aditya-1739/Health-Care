from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.appointment import Appointment
from app.schemas.appointment import AlternativeSlot, AlternativeSlotsResponse
from app.services.availability import calculate_doctor_availability


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def find_alternative_slots(
    db: Session,
    appointment_id: int,
    search_days_before: int = 2,
    search_days_after: int = 7,
    max_suggestions: int = 5,
) -> AlternativeSlotsResponse:
    """
    Find and rank alternative available slots for an appointment (e.g. if affected by leave).
    
    Ranking algorithm:
    - Score = (Distance in days * 100) + (Distance in minutes from original time of day)
    - Lower score is better.
    """
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    doctor = appointment.doctor
    doctor_name = doctor.user.name if doctor and doctor.user else f"Doctor #{doctor.id}"
    original_start = ensure_utc(appointment.start_time)
    original_date = original_start.date()
    original_minutes_of_day = original_start.hour * 60 + original_start.minute

    candidates: List[AlternativeSlot] = []

    start_date = max(date.today(), original_date - timedelta(days=search_days_before))
    end_date = original_date + timedelta(days=search_days_after)

    current_date = start_date
    while current_date <= end_date:
        # Get dynamic availability for the candidate date
        availability = calculate_doctor_availability(db, doctor.id, current_date)
        for slot in availability.slots:
            if not slot.available:
                continue

            # Don't suggest the exact same original slot
            if slot.start_time == original_start:
                continue

            slot_minutes_of_day = slot.start_time.hour * 60 + slot.start_time.minute
            day_diff = abs((current_date - original_date).days)
            time_diff = abs(slot_minutes_of_day - original_minutes_of_day)

            # Combined distance score (closest day prioritized, then closest time)
            score = (day_diff * 100.0) + (time_diff / 10.0)

            reason_desc = (
                f"Same day (+{time_diff} mins)" if day_diff == 0
                else f"{day_diff} day(s) difference"
            )

            candidates.append(
                AlternativeSlot(
                    start_time=slot.start_time,
                    end_time=slot.end_time,
                    doctor_id=doctor.id,
                    doctor_name=doctor_name,
                    score=score,
                    reason=reason_desc,
                )
            )

        current_date += timedelta(days=1)

    # Sort candidates by lowest distance score
    candidates.sort(key=lambda s: s.score)

    return AlternativeSlotsResponse(
        appointment_id=appointment.id,
        original_start_time=original_start,
        suggestions=candidates[:max_suggestions],
    )
