from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.deps import get_current_user, log_audit
from app.core.rate_limit import rate_limiter
from app.models.user import User
from app.schemas.calendar import (
    CalendarAuthUrlResponse,
    CalendarCallbackRequest,
    CalendarStatusResponse,
)
from app.services.calendar_service import CalendarService

router = APIRouter(prefix="/calendar", tags=["Google Calendar"])


@router.get(
    "/auth-url",
    response_model=CalendarAuthUrlResponse,
    summary="Get Google Calendar OAuth authorization URL",
)
def get_google_auth_url(
    current_user: User = Depends(get_current_user),
):
    """Generate authorization URL for connecting Google Calendar."""
    url = CalendarService.get_auth_url(current_user.id)
    return CalendarAuthUrlResponse(auth_url=url)


@router.post(
    "/callback",
    response_model=CalendarStatusResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limiter("calendar_callback", max_requests=10))],
    summary="Handle OAuth callback and store encrypted tokens",
)
def google_oauth_callback(
    payload: CalendarCallbackRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Exchange authorization code for tokens.
    Tokens are AES-256 encrypted before persistence.
    """
    token_record = CalendarService.handle_oauth_callback(db, current_user.id, payload.code)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="GOOGLE_CALENDAR_CONNECTED",
        resource="google_calendar_tokens",
        user_id=current_user.id,
        details={"status": token_record.connection_status.value},
        ip_address=client_ip,
    )

    return CalendarStatusResponse(
        connected=True,
        connection_status=token_record.connection_status,
        expires_at=token_record.expires_at,
    )


@router.get(
    "/status",
    response_model=CalendarStatusResponse,
    summary="Check Google Calendar connection status",
)
def get_calendar_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns calendar connection status.
    NEVER exposes access_token or refresh_token.
    """
    connected, conn_status, expires_at = CalendarService.get_connection_status(db, current_user.id)
    return CalendarStatusResponse(
        connected=connected,
        connection_status=conn_status,
        expires_at=expires_at,
    )


@router.delete(
    "/disconnect",
    summary="Disconnect Google Calendar",
)
def disconnect_calendar(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke and remove Google Calendar integration."""
    success = CalendarService.disconnect(db, current_user.id)

    client_ip = request.client.host if request.client else None
    log_audit(
        db=db,
        action="GOOGLE_CALENDAR_DISCONNECTED",
        resource="google_calendar_tokens",
        user_id=current_user.id,
        details={"disconnected": success},
        ip_address=client_ip,
    )

    return {"message": "Google Calendar disconnected successfully", "connected": False}
