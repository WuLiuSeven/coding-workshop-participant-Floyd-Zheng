from pydantic import BaseModel, ConfigDict

class FloorBase(BaseModel):
    '''
    '''
    floor_number: int
    building_id: int

class FloorRead(FloorBase):
    '''
    '''
    id : int
    model_config = ConfigDict(from_attributes=True)
