from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional, List

from api.deps import get_current_user
from core.firebase import ensure_initialized


class ClientCreate(BaseModel):
    name: str
    country: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    iban: Optional[str] = None
    notes: Optional[str] = None


class ClientResponse(ClientCreate):
    id: str


router = APIRouter(tags=["Clients"])


@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client(client: ClientCreate, user=Depends(get_current_user)):
    db = ensure_initialized()
    data = client.model_dump()
    data["user_uid"] = user["uid"]
    _, doc_ref = db.collection("clients").add(data)
    return ClientResponse(id=doc_ref.id, **data)


@router.get("/", response_model=List[ClientResponse])
def list_clients(user=Depends(get_current_user)):
    db = ensure_initialized()
    docs = db.collection("clients").where("user_uid", "==", user["uid"]).stream()
    return [ClientResponse(id=doc.id, **doc.to_dict()) for doc in docs]
