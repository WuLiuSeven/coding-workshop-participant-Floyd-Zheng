from pydantic import BaseModel, ConfigDict, Field
from app.models import Role

class UserBase(BaseModel):
    email: str = Field(min_length=2, max_length=100)
    first_name: str = Field(min_length=2, max_length=100)
    last_name: str = Field(min_length=2, max_length=100)
    is_active: bool = True
    role: Role

class UserCreate(UserBase):
    password: str = Field(min_length=8)

class UserRead(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
