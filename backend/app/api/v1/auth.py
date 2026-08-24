from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, log_audit
from app.core.rate_limit import rate_limiter
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import Patient, User, UserRole
from app.schemas.auth import (
    LoginRequest,
    RegisterPatientRequest,
    Token,
    UserProfileResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limiter("auth_register", max_requests=settings.RATE_LIMIT_AUTH_PER_MINUTE))],
    summary="Register a new patient account",
)
def register_patient(
    payload: RegisterPatientRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Self-registration is restricted strictly to PATIENT accounts.
    Doctor and Admin accounts must be provisioned by an administrator.
    """
    existing_user = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create base user
    new_user = User(
        name=payload.name.strip(),
        email=payload.email.lower().strip(),
        password_hash=get_password_hash(payload.password),
        role=UserRole.PATIENT,
        status="active",
    )
    db.add(new_user)
    db.flush()  # obtain user id

    # Create associated patient record
    patient = Patient(
        user_id=new_user.id,
        phone=payload.phone,
        date_of_birth=payload.date_of_birth,
    )
    db.add(patient)
    db.commit()
    db.refresh(new_user)

    # Record audit log
    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="REGISTER_PATIENT",
        resource="users",
        user_id=new_user.id,
        details={"email": new_user.email, "role": "PATIENT"},
        ip_address=client_ip,
    )

    return UserProfileResponse(
        id=new_user.id,
        name=new_user.name,
        email=new_user.email,
        role=new_user.role,
        status=new_user.status,
        patient_id=new_user.patient.id if new_user.patient else None,
        doctor_id=None,
    )


@router.post(
    "/login",
    response_model=Token,
    dependencies=[Depends(rate_limiter("auth_login", max_requests=settings.RATE_LIMIT_AUTH_PER_MINUTE))],
    summary="Authenticate user and receive JWT access token",
)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Validate credentials and return JWT bearer token with user role claims."""
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact support.",
        )

    # Create JWT
    token_str = create_access_token(
        subject=user.id,
        role=user.role.value,
    )

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="LOGIN_SUCCESS",
        resource="auth",
        user_id=user.id,
        details={"email": user.email, "role": user.role.value},
        ip_address=client_ip,
    )

    patient_id = user.patient.id if user.patient else None
    doctor_id = user.doctor.id if user.doctor else None

    return Token(
        access_token=token_str,
        token_type="bearer",
        user=UserProfileResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            status=user.status,
            patient_id=patient_id,
            doctor_id=doctor_id,
        ),
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current authenticated user profile",
)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Fetch current user identity and associated profile IDs."""
    patient_id = current_user.patient.id if current_user.patient else None
    doctor_id = current_user.doctor.id if current_user.doctor else None

    return UserProfileResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role,
        status=current_user.status,
        patient_id=patient_id,
        doctor_id=doctor_id,
    )


@router.post(
    "/logout",
    summary="Logout user session",
)
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Client-side token disposal. Logs logout audit event."""
    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="LOGOUT",
        resource="auth",
        user_id=current_user.id,
        details={"email": current_user.email},
        ip_address=client_ip,
    )
    return {"message": "Successfully logged out"}
