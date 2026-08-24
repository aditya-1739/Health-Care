from datetime import date, datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.deps import get_current_user, log_audit, require_patient
from app.core.security import get_password_hash, verify_password
from app.models.appointment import Appointment, AppointmentStatus
from app.models.records import SymptomForm, Prescription
from app.models.user import Doctor, Patient, PatientMedicalProfile, User, UserRole
from app.schemas.profile import (
    AdminUserDetailResponse,
    AppointmentHistoryItem,
    AppointmentHistoryResponse,
    ChangePasswordRequest,
    MedicalProfileResponse,
    MedicalProfileUpdate,
    UserProfileResponse,
    UserProfileUpdate,
    calculate_age,
)

router = APIRouter(prefix="/profile", tags=["Profile"])


def _build_user_profile_response(user: User) -> UserProfileResponse:
    patient_id = user.patient.id if user.patient else None
    doctor_id = user.doctor.id if user.doctor else None

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

    if user.patient:
        phone = user.patient.phone or phone
        dob = user.patient.date_of_birth or dob
        gender = user.patient.gender
        address = user.patient.address
        emergency_contact_name = user.patient.emergency_contact_name
        emergency_contact_phone = user.patient.emergency_contact_phone
    elif user.doctor:
        phone = user.doctor.phone or phone
        dob = user.doctor.date_of_birth or dob
        specialization = user.doctor.specialization
        bio = user.doctor.bio
        slot_duration = user.doctor.slot_duration
        active = user.doctor.active

    age = calculate_age(dob)

    return UserProfileResponse(
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
        patient_id=patient_id,
        doctor_id=doctor_id,
        created_at=user.created_at,
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current user's profile",
)
def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve full personal profile for the authenticated user."""
    # Ensure relationships are loaded
    user = (
        db.query(User)
        .options(joinedload(User.patient), joinedload(User.doctor))
        .filter(User.id == current_user.id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _build_user_profile_response(user)


@router.put(
    "/me",
    response_model=UserProfileResponse,
    summary="Update current user's profile",
)
def update_my_profile(
    payload: UserProfileUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update allowed personal profile fields according to user role."""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.name is not None and payload.name.strip():
        user.name = payload.name.strip()

    if payload.phone is not None:
        user.phone = payload.phone.strip() if payload.phone else None

    if payload.date_of_birth is not None:
        user.date_of_birth = payload.date_of_birth

    if user.role == UserRole.PATIENT and user.patient:
        if payload.phone is not None:
            user.patient.phone = payload.phone.strip() if payload.phone else None
        if payload.date_of_birth is not None:
            user.patient.date_of_birth = payload.date_of_birth
        if payload.gender is not None:
            user.patient.gender = payload.gender
        if payload.address is not None:
            user.patient.address = payload.address
        if payload.emergency_contact_name is not None:
            user.patient.emergency_contact_name = payload.emergency_contact_name
        if payload.emergency_contact_phone is not None:
            user.patient.emergency_contact_phone = payload.emergency_contact_phone
    elif user.role == UserRole.DOCTOR and user.doctor:
        if payload.phone is not None:
            user.doctor.phone = payload.phone.strip() if payload.phone else None
        if payload.date_of_birth is not None:
            user.doctor.date_of_birth = payload.date_of_birth
        if payload.bio is not None:
            user.doctor.bio = payload.bio
        if payload.specialization is not None and payload.specialization.strip():
            user.doctor.specialization = payload.specialization.strip()

    db.commit()
    db.refresh(user)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="UPDATE_PROFILE",
        resource="users",
        user_id=user.id,
        details={"updates": payload.model_dump(mode="json", exclude_unset=True, exclude_none=True)},
        ip_address=client_ip,
    )

    return _build_user_profile_response(user)


@router.get(
    "/me/medical",
    response_model=MedicalProfileResponse,
    summary="Get current patient's medical profile",
)
def get_my_medical_profile(
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """Retrieve sensitive medical profile for authenticated patient."""
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient record not found")

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


@router.put(
    "/me/medical",
    response_model=MedicalProfileResponse,
    summary="Update current patient's medical profile",
)
def update_my_medical_profile(
    payload: MedicalProfileUpdate,
    request: Request,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """Create or update patient medical profile."""
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient record not found")

    med_profile = (
        db.query(PatientMedicalProfile)
        .filter(PatientMedicalProfile.patient_id == patient.id)
        .first()
    )

    if not med_profile:
        med_profile = PatientMedicalProfile(patient_id=patient.id)
        db.add(med_profile)

    if payload.blood_group is not None:
        med_profile.blood_group = payload.blood_group.strip().upper() if payload.blood_group else None
    if payload.height_cm is not None:
        med_profile.height_cm = payload.height_cm
    if payload.weight_kg is not None:
        med_profile.weight_kg = payload.weight_kg
    if payload.allergies is not None:
        med_profile.allergies = payload.allergies.strip() if payload.allergies else None
    if payload.chronic_conditions is not None:
        med_profile.chronic_conditions = payload.chronic_conditions.strip() if payload.chronic_conditions else None
    if payload.current_medications is not None:
        med_profile.current_medications = payload.current_medications.strip() if payload.current_medications else None
    if payload.past_surgeries is not None:
        med_profile.past_surgeries = payload.past_surgeries.strip() if payload.past_surgeries else None
    if payload.family_history is not None:
        med_profile.family_history = payload.family_history.strip() if payload.family_history else None
    if payload.medical_notes is not None:
        med_profile.medical_notes = payload.medical_notes.strip() if payload.medical_notes else None

    db.commit()
    db.refresh(med_profile)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="UPDATE_MEDICAL_PROFILE",
        resource="patient_medical_profiles",
        user_id=current_user.id,
        details={"patient_id": patient.id},
        ip_address=client_ip,
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


@router.get(
    "/me/appointments",
    response_model=AppointmentHistoryResponse,
    summary="Get user's categorized appointment history",
)
def get_my_appointment_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve appointments organized into Upcoming, Past, and Cancelled."""
    now_utc = datetime.now(timezone.utc)

    query = (
        db.query(Appointment)
        .options(
            joinedload(Appointment.doctor).joinedload(Doctor.user),
            joinedload(Appointment.patient).joinedload(Patient.user),
            joinedload(Appointment.symptom_form),
            joinedload(Appointment.prescription),
        )
    )

    if current_user.role == UserRole.PATIENT:
        if not current_user.patient:
            return AppointmentHistoryResponse(upcoming=[], past=[], cancelled=[], total=0)
        query = query.filter(Appointment.patient_id == current_user.patient.id)
    elif current_user.role == UserRole.DOCTOR:
        if not current_user.doctor:
            return AppointmentHistoryResponse(upcoming=[], past=[], cancelled=[], total=0)
        query = query.filter(Appointment.doctor_id == current_user.doctor.id)
    elif current_user.role == UserRole.ADMIN:
        pass

    all_appointments = query.order_by(Appointment.start_time.desc()).all()

    upcoming_list = []
    past_list = []
    cancelled_list = []

    for appt in all_appointments:
        doc_user = appt.doctor.user if appt.doctor else None
        pat_user = appt.patient.user if appt.patient else None

        doc_name = doc_user.name if doc_user else f"Doctor #{appt.doctor_id}"
        spec = appt.doctor.specialization if appt.doctor else "General"
        pat_name = pat_user.name if pat_user else f"Patient #{appt.patient_id}"

        chief = appt.symptom_form.chief_complaint if appt.symptom_form else None
        has_rx = appt.prescription is not None

        item = AppointmentHistoryItem(
            id=appt.id,
            doctor_id=appt.doctor_id,
            doctor_name=doc_name,
            doctor_specialization=spec,
            patient_id=appt.patient_id,
            patient_name=pat_name,
            start_time=appt.start_time,
            end_time=appt.end_time,
            status=appt.status.value,
            cancellation_reason=appt.cancellation_reason,
            decline_remarks=appt.cancellation_reason if appt.status == AppointmentStatus.CANCELLED else None,
            chief_complaint=chief,
            has_prescription=has_rx,
            created_at=appt.created_at,
        )

        start_dt = appt.start_time
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)

        if appt.status in [AppointmentStatus.CANCELLED, AppointmentStatus.EXPIRED]:
            cancelled_list.append(item)
        elif appt.status in [AppointmentStatus.CONFIRMED, AppointmentStatus.HELD] and start_dt >= now_utc:
            upcoming_list.append(item)
        else:
            past_list.append(item)

    return AppointmentHistoryResponse(
        upcoming=upcoming_list,
        past=past_list,
        cancelled=cancelled_list,
        total=len(all_appointments),
    )


@router.post(
    "/me/change-password",
    summary="Change current user's password",
)
@router.put(
    "/me/password",
    summary="Change current user's password (PUT alias)",
)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Validate current password and update to new password."""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password",
        )

    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    user.password_hash = get_password_hash(payload.new_password)
    db.commit()

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="CHANGE_PASSWORD",
        resource="auth",
        user_id=user.id,
        details={"email": user.email},
        ip_address=client_ip,
    )

    return {"message": "Password changed successfully. Please sign in again."}
