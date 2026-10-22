from pydantic import BaseModel, ConfigDict, Field
from app.models import Team

class EngineerBase(BaseModel):
    '''
    '''
    is_available: bool
    at_incident: int | None
    team: Team
    user_id: int

class EngineerRead(EngineerBase):
    '''
    '''
    id : int
    model_config = ConfigDict(from_attributes=True)
