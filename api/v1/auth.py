# API роутер для автентифікації

from fastapi import APIRouter, HTTPException, status, Depends
from firebase_admin.auth import EmailAlreadyExistsError

from models.user import UserCreate, UserInDB, UserUpdate
from services import auth_service
from core.firebase import auth_client, db, ensure_initialized
from api.deps import get_current_user
from pydantic import BaseModel
from typing import List

class UserGoogleCreate(BaseModel):
    uid: str
    email: str
    first_name: str
    last_name: str
    phone: str | None = None
    middle_name: str | None = None

class OnboardingPayload(BaseModel):
    firstName: str
    lastName: str
    middleName: str | None = None
    taxId: str
    email: str
    phone: str | None = None
    taxGroup: str
    paysESV: bool
    selectedKveds: List[str]

router = APIRouter()

@router.post(
    "/google", 
    response_model=UserInDB, 
    status_code=status.HTTP_200_OK
)
def google_auth_upsert(user_data: UserGoogleCreate):
    """
    "Upsert" для користувача Google.
    Перевіряє, чи існує профіль у Firestore.
    - Якщо так: повертає його.
    - Якщо ні: створює новий профіль і повертає його.
    """
    try:
        # 1. Перевіряємо, чи існує профіль
        existing_profile = auth_service.get_user_profile(user_data.uid)
        
        if existing_profile:
            # Користувач вже існує, просто повертаємо профіль
            return existing_profile
            
        # 2. Якщо профілю немає - створюємо його
        new_profile = auth_service.create_user_profile(
            uid=user_data.uid,
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            middle_name=user_data.middle_name,
            phone=user_data.phone,
        )
        return new_profile

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/register", response_model=UserInDB, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserCreate):
    """
    Створює користувача одночасно в Firebase Authentication
    та в базі даних Firestore.
    """
    try:
        # 1. Створюємо користувача в Firebase Authentication
        user_record = auth_client.create_user(
            email=user_data.email,
            password=user_data.password,
            display_name=f"{user_data.first_name} {user_data.last_name}"
        )

        # 2. Створюємо профіль користувача в Firestore
        user_profile = auth_service.create_user_profile(
            uid=user_record.uid,
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            middle_name=getattr(user_data, "middle_name", None) if hasattr(user_data, "middle_name") else None,
            phone=user_data.phone,
        )
        return user_profile

    except EmailAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/me", response_model=UserInDB)
def get_user_me(current_user: dict = Depends(get_current_user)):
    """
    Отримує профіль поточного користувача з Firestore.
    Використовує 'uid' з перевіреного токена.
    """
    uid = current_user.get("uid")
    user_profile = auth_service.get_user_profile(uid)

    if user_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found in Firestore"
        )
    return user_profile

@router.put("/me", response_model=UserInDB)
def update_user_me(
    user_data: UserUpdate, # 1. Принимаем 'first_name', 'last_name'
    current_user: dict = Depends(get_current_user) # 2. Проверяем, что пользователь "вошел"
):
    """
    Обновляет имя и фамилию текущего пользователя.
    """
    uid = current_user.get("uid")
    
    # 3. Вызываем наш новый "мозг"
    updated_profile = auth_service.update_user_profile(uid, user_data)
    
    if updated_profile is None:
         raise HTTPException(
            status_code=404, 
            detail="Не удалось найти профиль после обновления."
        )
    
    # 4. Возвращаем обновленный профиль фронтенду
    return updated_profile

@router.post("/onboarding", response_model=UserInDB)
def complete_onboarding(
    onboarding_data: OnboardingPayload,
    current_user: dict = Depends(get_current_user)
):
    """
    Зберігає результат онбордингу в профілі користувача.
    """
    uid = current_user.get("uid")
    local_db = ensure_initialized()
    try:
        doc_ref = local_db.collection("users").document(uid)
        doc_ref.update({
            "onboarding_completed": True,
            "onboarding_data": onboarding_data.dict(),
            "first_name": onboarding_data.firstName or current_user.get("name", ""),
            "last_name": onboarding_data.lastName,
            "middle_name": onboarding_data.middleName,
            "phone": onboarding_data.phone,
        })
        # Повертаємо оновлений профіль
        updated_profile = auth_service.get_user_profile(uid)
        return updated_profile
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не вдалося зберегти онбординг: {e}"
        )
