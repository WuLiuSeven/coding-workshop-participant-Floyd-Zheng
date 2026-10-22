
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class TicketBase(BaseModel):
    engineer_id: int
    incident_id: int


class TicketRead(TicketBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TicketUpdate(BaseModel):
    engineer_id: int | None = None
    incident_id: int | None = None
