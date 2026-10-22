from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class NoteBase(BaseModel):
    comments: str | None = Field(default=None, max_length=250)
    incident_at: int


class NoteUpdate(BaseModel):
    comments: str | None = None
    incident_at: int | None = None


class NoteRead(NoteBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
