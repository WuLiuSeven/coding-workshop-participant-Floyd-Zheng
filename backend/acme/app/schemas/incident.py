from pydantic import BaseModel, ConfigDict
from datetime import datetime
from app.models import Priority, Status, Category


class IncidentBase(BaseModel):
    status: Status
    priority: Priority
    category: Category
    is_escalated: bool = False
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    resolved_by: int | None = None
    seat_id: int
    incident_notes: str | None = None


class IncidentRead(IncidentBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class IncidentUpdate(BaseModel):
    status: Status | None = None
    priority: Priority | None = None
    category: Category | None = None
    is_escalated: bool | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    reported_by: int | None = None
    resolved_by: int | None = None
    seat_id: int | None = None
    incident_notes: str | None = None