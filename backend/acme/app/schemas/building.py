from pydantic import BaseModel, ConfigDict, Field

class BuildingBase(BaseModel):
    '''
    '''
    name: str = Field(min_length = 1, max_length = 100)
    facility_id: int

class BuildingRead(BuildingBase):
    '''
    '''
    id : int
    model_config = ConfigDict(from_attributes=True)
