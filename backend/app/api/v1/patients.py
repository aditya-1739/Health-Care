from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user, require_patient
from app.models.appointment import Appointment
from app.models.user import Patient, PatientMedicalProfile, User, UserRole
from app.schemas.patient import PatientResponse, PatientUpdate
from app.schemas.profile import MedicalProfileResponse

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get(
    "/me",
    response_model=PatientResponse,
    summary="Get current patient's profile",
)
def get_my_patient_profile(
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """Retrieve personal health profile for the authenticated patient."""
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found",
        )

    return PatientResponse(
        id=patient.id,
        user_id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        phone=patient.phone,
        date_of_birth=patient.date_of_birth,
        preferences=patient.preferences,
        created_at=patient.created_at,
    )


@router.put(
    "/me",
    response_model=PatientResponse,
    summary="Update current patient's profile",
)
def update_my_patient_profile(
    payload: PatientUpdate,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """Update personal contact info, DOB, and preferences."""
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient profile not found",
        )

    if payload.phone is not None:
        patient.phone = payload.phone
    if payload.date_of_birth is not None:
        patient.date_of_birth = payload.date_of_birth
    if payload.preferences is not None:
        patient.preferences = payload.preferences

    db.commit()
    db.refresh(patient)

    return PatientResponse(
        id=patient.id,
        user_id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        phone=patient.phone,
        date_of_birth=patient.date_of_birth,
        preferences=patient.preferences,
        created_at=patient.created_at,
    )


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    summary="Get patient profile by ID (Strictly isolated)",
)
def get_patient_by_id(
    patient_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Data Isolation Rule:
    - PATIENT can ONLY access their own record.
    - DOCTOR can ONLY access if an appointment relationship exists.
    - ADMIN has administrative access.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient record not found",
        )

    # Authorization Check
    if current_user.role == UserRole.PATIENT:
        if not current_user.patient or current_user.patient.id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Patients cannot access other patients' records",
            )
    elif current_user.role == UserRole.DOCTOR:
        doctor = current_user.doctor
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Doctor profile missing",
            )
        # Check if an appointment exists between this doctor and the requested patient
        has_appointment = (
            db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor.id,
                Appointment.patient_id == patient_id,
            )
            .first()
        )
        if not has_appointment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: No clinical relationship with this patient",
            )
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Insufficient privileges",
        )

    patient_user = patient.user
    return PatientResponse(
        id=patient.id,
        user_id=patient.user_id,
        name=patient_user.name if patient_user else "",
        email=patient_user.email if patient_user else "",
        phone=patient.phone,
        date_of_birth=patient.date_of_birth,
        preferences=patient.preferences,
        created_at=patient.created_at,
    )


@router.get(
    "/{patient_id}/medical",
    response_model=MedicalProfileResponse,
    summary="Get patient medical profile (Strictly authorized)",
)
def get_patient_medical_profile(
    patient_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Medical Profile Data Isolation:
    - PATIENT can ONLY access own medical profile.
    - DOCTOR can ONLY access if an active or past appointment exists with this patient.
    - ADMIN has administrative access.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient record not found",
        )

    if current_user.role == UserRole.PATIENT:
        if not current_user.patient or current_user.patient.id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Patients cannot access other patients' medical profiles",
            )
    elif current_user.role == UserRole.DOCTOR:
        doctor = current_user.doctor
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Doctor profile missing",
            )
        has_appointment = (
            db.query(Appointment)
            .filter(
                Appointment.doctor_id == doctor.id,
                Appointment.patient_id == patient_id,
            )
            .first()
        )
        if not has_appointment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: No clinical relationship with this patient",
            )
    elif current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Insufficient privileges",
        )

    med_profile = (
        db.query(PatientMedicalProfile)
        .filter(PatientMedicalProfile.patient_id == patient.id)
        .first()
    )

    if not med_profile:
        return MedicalProfileResponse(
            id=None,
            patient_id=patient.id,
            blood_group=None,
            height_cm=None,
            weight_kg=None,
            allergies=None,
            chronic_conditions=None,
            current_medications=None,
            past_surgeries=None,
            family_history=None,
            medical_notes=None,
            created_at=None,
            updated_at=None,
        )

    return MedicalProfileResponse(
        id=med_profile.id,
        patient_id=patient.id,
        blood_group=med_profile.blood_group,
        height_cm=med_profile.height_cm,
        weight_kg=med_profile.weight_kg,
        allergies=med_profile.allergies,
        chronic_conditions=med_profile.chronic_conditions,
        current_medications=med_profile.current_medications,
        past_surgeries=med_profile.past_surgeries,
        family_history=med_profile.family_history,
        medical_notes=med_profile.medical_notes,
        created_at=med_profile.created_at,
        updated_at=med_profile.updated_at,
    )
