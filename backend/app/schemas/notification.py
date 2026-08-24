from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict
from app.models.records import NotificationStatus


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    appointment_id: Optional[int] = None
    type: str
    event_type: str
    recipient_email: str
    subject: str
    status: NotificationStatus
    retry_count: int
    next_retry_at: Optional[datetime] = None
    last_error: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReliabilityMetricsResponse(BaseModel):
    ai_jobs: Dict[str, int]
    notifications: Dict[str, int]
    medication_reminders: Dict[str, int]
    calendar_syncs: Dict[str, int]
