from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user, log_audit, require_doctor, require_patient
from app.models.appointment import Appointment, AppointmentStatus
from app.models.records import (
    AIJobStatus,
    AISummary,
    AISummaryType,
    ClinicalNote,
    MedicationReminder,
    MedicationStatus,
    Prescription,
    PrescriptionMedication,
    PrescriptionStatus,
    SymptomForm,
)
from app.models.user import User, UserRole
from app.schemas.clinical import (
    AISummaryResponse,
    ClinicalNoteCreate,
    ClinicalNoteResponse,
    DoseItem,
    MedicationIntakeResponse,
    MedicationReminderResponse,
    MedicationScheduleResponse,
    PrescriptionCreate,
    PrescriptionMedicationResponse,
    PrescriptionMedicationStatusUpdate,
    PrescriptionResponse,
    SymptomFormCreate,
    SymptomFormResponse,
)
from app.core.config import settings
from app.core.rate_limit import rate_limiter
from app.services.background_tasks import enqueue_task
from app.services.medication_service import MedicationService

router = APIRouter(prefix="", tags=["Clinical Workflow"])


# -----------------------------------------------------------------------------
# 1. Patient Symptom Intake
# -----------------------------------------------------------------------------

@router.post(
    "/appointments/{appointment_id}/symptoms",
    response_model=SymptomFormResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter("clinical_symptoms", max_requests=settings.RATE_LIMIT_AI_PER_MINUTE))],
    summary="Submit patient symptoms for an appointment",
)
def submit_symptoms(
    appointment_id: int,
    payload: SymptomFormCreate,
    request: Request,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """
    Patient submits symptoms before an appointment.
    Original symptoms are saved and never modified by AI.
    Triggers asynchronous Pre-Visit AI Summary generation.
    """
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if not current_user.patient or appointment.patient_id != current_user.patient.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: You can only submit symptoms for your own appointments",
        )

    symptom_form = (
        db.query(SymptomForm)
        .filter(SymptomForm.appointment_id == appointment_id)
        .first()
    )
    if not symptom_form:
        symptom_form = SymptomForm(
            appointment_id=appointment_id,
            symptoms=payload.symptoms,
            chief_complaint=payload.chief_complaint,
            additional_notes=payload.additional_notes,
        )
        db.add(symptom_form)
    else:
        symptom_form.symptoms = payload.symptoms
        symptom_form.chief_complaint = payload.chief_complaint
        symptom_form.additional_notes = payload.additional_notes

    db.commit()
    db.refresh(symptom_form)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="SYMPTOM_SUBMITTED",
        resource="symptom_forms",
        user_id=current_user.id,
        details={"appointment_id": appointment_id},
        ip_address=client_ip,
    )

    # Trigger Async Pre-Visit AI Summary job
    enqueue_task("GENERATE_PREVISIT_AI", {"appointment_id": appointment_id})

    return symptom_form


@router.get(
    "/appointments/{appointment_id}/symptoms",
    response_model=SymptomFormResponse,
    summary="Get patient symptoms for an appointment",
)
def get_symptoms(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve submitted symptoms with role isolation."""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Authorization Check
    if current_user.role == UserRole.PATIENT:
        if not current_user.patient or appointment.patient_id != current_user.patient.id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role == UserRole.DOCTOR:
        if not current_user.doctor or appointment.doctor_id != current_user.doctor.id:
            raise HTTPException(status_code=403, detail="Access denied")

    symptom_form = (
        db.query(SymptomForm)
        .filter(SymptomForm.appointment_id == appointment_id)
        .first()
    )
    if not symptom_form:
        raise HTTPException(status_code=404, detail="No symptoms recorded for this appointment")

    return symptom_form


# -----------------------------------------------------------------------------
# 2. AI Summaries Viewer
# -----------------------------------------------------------------------------

@router.get(
    "/appointments/{appointment_id}/ai-summary",
    response_model=List[AISummaryResponse],
    summary="Get AI Pre-Visit and Post-Visit summaries",
)
def get_ai_summaries(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """View AI summaries generated for an appointment."""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if current_user.role == UserRole.PATIENT:
        if not current_user.patient or appointment.patient_id != current_user.patient.id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role == UserRole.DOCTOR:
        if not current_user.doctor or appointment.doctor_id != current_user.doctor.id:
            raise HTTPException(status_code=403, detail="Access denied")

    summaries = (
        db.query(AISummary)
        .filter(AISummary.appointment_id == appointment_id)
        .order_by(AISummary.created_at.asc())
        .all()
    )
    return summaries


# -----------------------------------------------------------------------------
# 3. Clinical Notes (Doctor Authoritative Record)
# -----------------------------------------------------------------------------

@router.post(
    "/appointments/{appointment_id}/clinical-notes",
    response_model=ClinicalNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Doctor saves authoritative clinical notes and diagnosis",
)
def save_clinical_notes(
    appointment_id: int,
    payload: ClinicalNoteCreate,
    request: Request,
    current_user: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    """
    Doctor records authoritative clinical assessment and diagnosis.
    AI is strictly forbidden from modifying or overwriting this record.
    """
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if not current_user.doctor or appointment.doctor_id != current_user.doctor.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: You can only record notes for your assigned appointments",
        )

    clinical_note = (
        db.query(ClinicalNote)
        .filter(ClinicalNote.appointment_id == appointment_id)
        .first()
    )
    if not clinical_note:
        clinical_note = ClinicalNote(
            appointment_id=appointment_id,
            doctor_id=current_user.doctor.id,
            notes=payload.notes,
            diagnosis=payload.diagnosis,
        )
        db.add(clinical_note)
    else:
        clinical_note.notes = payload.notes
        if payload.diagnosis is not None:
            clinical_note.diagnosis = payload.diagnosis

    db.commit()
    db.refresh(clinical_note)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="CLINICAL_NOTE_SAVED",
        resource="clinical_notes",
        user_id=current_user.id,
        details={"appointment_id": appointment_id, "has_diagnosis": bool(payload.diagnosis)},
        ip_address=client_ip,
    )

    # Trigger Post-Visit AI Summary generation
    enqueue_task("GENERATE_POSTVISIT_AI", {"appointment_id": appointment_id})

    return clinical_note


@router.get(
    "/appointments/{appointment_id}/clinical-notes",
    response_model=ClinicalNoteResponse,
    summary="Get clinical notes for an appointment",
)
def get_clinical_notes(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """View clinical notes with patient/doctor isolation."""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if current_user.role == UserRole.PATIENT:
        if not current_user.patient or appointment.patient_id != current_user.patient.id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role == UserRole.DOCTOR:
        if not current_user.doctor or appointment.doctor_id != current_user.doctor.id:
            raise HTTPException(status_code=403, detail="Access denied")

    clinical_note = (
        db.query(ClinicalNote)
        .filter(ClinicalNote.appointment_id == appointment_id)
        .first()
    )
    if not clinical_note:
        raise HTTPException(status_code=404, detail="No clinical notes found for this appointment")

    return clinical_note


# -----------------------------------------------------------------------------
# 4. Structured Prescriptions & Medications
# -----------------------------------------------------------------------------

@router.post(
    "/appointments/{appointment_id}/prescription",
    response_model=PrescriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Doctor creates structured prescription with multiple medications",
)
def create_prescription(
    appointment_id: int,
    payload: PrescriptionCreate,
    request: Request,
    current_user: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    """
    Doctor creates or updates structured prescription with normalized medications.
    Preserves versioning and generates medication reminders.
    """
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if not current_user.doctor or appointment.doctor_id != current_user.doctor.id:
        raise HTTPException(status_code=403, detail="Access denied: Not your assigned appointment")

    prescription = (
        db.query(Prescription)
        .filter(Prescription.appointment_id == appointment_id)
        .first()
    )

    if not prescription:
        prescription = Prescription(
            appointment_id=appointment_id,
            doctor_id=current_user.doctor.id,
            patient_id=appointment.patient_id,
            version=1,
            status=PrescriptionStatus.ACTIVE,
            general_instructions=payload.general_instructions,
        )
        db.add(prescription)
        db.flush()
    else:
        # Versioning: increment version when modified
        prescription.version += 1
        prescription.status = PrescriptionStatus.MODIFIED
        prescription.general_instructions = payload.general_instructions

    # Add medication items
    for med_in in payload.medications:
        med_item = PrescriptionMedication(
            prescription_id=prescription.id,
            name=med_in.name,
            dosage=med_in.dosage,
            frequency=med_in.frequency,
            start_date=med_in.start_date,
            end_date=med_in.end_date,
            instructions=med_in.instructions,
            status=MedicationStatus.ACTIVE,
        )
        db.add(med_item)
        db.flush()

        # Generate discrete reminder instances for this medication
        MedicationService.generate_reminders_for_medication(
            db=db,
            medication_id=med_item.id,
            patient_id=appointment.patient_id,
        )

    db.commit()
    db.refresh(prescription)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="PRESCRIPTION_CREATED",
        resource="prescriptions",
        user_id=current_user.id,
        details={"appointment_id": appointment_id, "medication_count": len(payload.medications), "version": prescription.version},
        ip_address=client_ip,
    )

    # Trigger Post-Visit AI Summary update
    enqueue_task("GENERATE_POSTVISIT_AI", {"appointment_id": appointment_id})

    return prescription


@router.get(
    "/appointments/{appointment_id}/prescription",
    response_model=PrescriptionResponse,
    summary="Get structured prescription for an appointment",
)
def get_prescription(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """View structured prescription with patient/doctor isolation."""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if current_user.role == UserRole.PATIENT:
        if not current_user.patient or appointment.patient_id != current_user.patient.id:
            raise HTTPException(status_code=403, detail="Access denied")
    elif current_user.role == UserRole.DOCTOR:
        if not current_user.doctor or appointment.doctor_id != current_user.doctor.id:
            raise HTTPException(status_code=403, detail="Access denied")

    prescription = (
        db.query(Prescription)
        .filter(Prescription.appointment_id == appointment_id)
        .first()
    )
    if not prescription:
        raise HTTPException(status_code=404, detail="No prescription recorded for this appointment")

    return prescription


@router.patch(
    "/prescriptions/{prescription_id}/medications/{medication_id}/status",
    response_model=PrescriptionMedicationResponse,
    summary="Update or discontinue an individual medication item",
)
def update_medication_status(
    prescription_id: int,
    medication_id: int,
    payload: PrescriptionMedicationStatusUpdate,
    current_user: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    """Doctor discontinues or completes an individual medication."""
    medication = (
        db.query(PrescriptionMedication)
        .filter(
            PrescriptionMedication.id == medication_id,
            PrescriptionMedication.prescription_id == prescription_id,
        )
        .first()
    )
    if not medication:
        raise HTTPException(status_code=404, detail="Medication record not found")

    medication.status = payload.status
    if payload.status in (MedicationStatus.DISCONTINUED, MedicationStatus.COMPLETED):
        MedicationService.cancel_reminders_for_medication(db, medication.id)

    db.commit()
    db.refresh(medication)
    return medication


# -----------------------------------------------------------------------------
# 5. Patient Medication Reminder Schedule
# -----------------------------------------------------------------------------

@router.get(
    "/patients/me/medication-reminders",
    response_model=List[MedicationReminderResponse],
    summary="Get upcoming medication reminders for the authenticated patient",
)
def get_my_medication_reminders(
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """Patient views their upcoming medication reminder schedule."""
    if not current_user.patient:
        return []

    reminders = (
        db.query(MedicationReminder)
        .filter(MedicationReminder.patient_id == current_user.patient.id)
        .order_by(MedicationReminder.scheduled_at.asc())
        .all()
    )
    results = []
    for r in reminders:
        intake_stat = r.intake.status.value if r.intake and hasattr(r.intake.status, "value") else (str(r.intake.status) if r.intake else None)
        taken_time = r.intake.taken_at if (r.intake and intake_stat == "TAKEN") else None
        results.append(
            MedicationReminderResponse(
                id=r.id,
                prescription_medication_id=r.prescription_medication_id,
                patient_id=r.patient_id,
                medication_name=r.medication_name,
                dosage=r.dosage,
                scheduled_at=r.scheduled_at,
                status=r.status,
                sent_at=r.sent_at,
                intake_status=intake_stat,
                taken_at=taken_time,
                created_at=r.created_at,
            )
        )
    return results


@router.post(
    "/patients/me/medication-reminders/{reminder_id}/taken",
    response_model=MedicationIntakeResponse,
    summary="Mark a scheduled medication reminder as taken",
)
def mark_reminder_as_taken(
    reminder_id: int,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """
    Patient marks a scheduled medication dose as taken.
    Guarantees:
    - Authenticated PATIENT role.
    - Patient isolation: Verifies reminder belongs to authenticated patient.
    - Idempotent: repeated clicks return existing taken intake record without duplicate entries.
    """
    if not current_user.patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found",
        )

    try:
        result = MedicationService.record_intake(
            db=db,
            reminder_id=reminder_id,
            patient_id=current_user.patient.id,
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: medication reminder belongs to another patient",
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Medication reminder not found",
        )

    intake, reminder, is_new = result
    return MedicationIntakeResponse(
        id=intake.id,
        reminder_id=reminder.id,
        patient_id=intake.patient_id,
        medication_name=reminder.medication_name,
        dosage=reminder.dosage,
        scheduled_at=intake.scheduled_at,
        taken_at=intake.taken_at,
        status=intake.status.value if hasattr(intake.status, "value") else str(intake.status),
        notes=intake.notes,
        created_at=intake.created_at,
        updated_at=intake.updated_at,
    )


@router.get(
    "/patients/me/medication-schedule",
    response_model=MedicationScheduleResponse,
    summary="Get structured medication schedule, next dose countdown, today's doses, and history",
)
def get_my_medication_schedule(
    tz_offset_hours: int = 0,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """
    Get patient-centric structured medication schedule:
    - next_dose: Earliest due / upcoming pending dose with countdown target.
    - today_doses: Chronological doses for today in patient's timezone.
    - upcoming_doses: Next future doses.
    - active_medications: Active prescription courses and remaining doses.
    - history: Completed/taken and missed doses.
    """
    if not current_user.patient:
        return MedicationScheduleResponse()

    schedule_data = MedicationService.get_patient_schedule(
        db=db,
        patient_id=current_user.patient.id,
        tz_offset_hours=tz_offset_hours,
    )
    return schedule_data

