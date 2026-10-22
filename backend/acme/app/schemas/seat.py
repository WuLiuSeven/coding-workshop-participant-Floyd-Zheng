from pydantic import BaseModel, ConfigDict

class SeatBase(BaseModel):
    '''
    '''
    seat_number: int | None
    floor_id: int

class SeatRead(SeatBase):
    '''
    '''
    id : int
    model_config = ConfigDict(from_attributes=True)
