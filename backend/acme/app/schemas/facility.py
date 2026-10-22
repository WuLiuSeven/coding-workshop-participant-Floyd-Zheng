from pydantic import BaseModel, ConfigDict, Field

class FacilityBase(BaseModel):
    '''
    '''
    name: str = Field(min_length = 1, max_length = 100)

class FacilityRead(FacilityBase):
    '''
    '''
    id : int
    model_config = ConfigDict(from_attributes=True)
