from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.records import CalendarConnectionStatus, CalendarSyncStatus


class CalendarAuthUrlResponse(BaseModel):
    auth_url: str


class CalendarCallbackRequest(BaseModel):
    code: str


class CalendarStatusResponse(BaseModel):
    connected: bool
    connection_status: CalendarConnectionStatus
    expires_at: Optional[datetime] = None


class CalendarEventResponse(BaseModel):
    id: int
    appointment_id: int
    user_id: int
    provider: str
    google_event_id: Optional[str] = None
    sync_status: CalendarSyncStatus
    retry_count: int
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
