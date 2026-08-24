from datetime import date, datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, EmailStr


class PatientResponse(BaseModel):
    id: int
    user_id: int
    name: str
    email: EmailStr
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    preferences: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PatientUpdate(BaseModel):
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    preferences: Optional[Dict[str, Any]] = None
