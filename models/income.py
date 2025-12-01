from pydantic import BaseModel

class IncomeCreate(BaseModel):
    amount: float
    description: str
    date: str # (або datetime)

class IncomeInDB(IncomeCreate):
    id: str
    user_uid: str