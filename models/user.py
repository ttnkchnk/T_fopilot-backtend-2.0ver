# Pydantic моделі для даних користувача

from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    middle_name: str | None = None
    phone: str | None = None

class UserCreate(UserBase):
    password: str

class UserInDB(UserBase):
    uid: str
    fop_group: int = 3
    tax_rate: float = 0.05
    onboarding_completed: bool = False
    onboarding_data: dict | None = None

class UserUpdate(BaseModel):
    first_name: str
    last_name: str
    middle_name: str | None = None
    phone: str | None = None
