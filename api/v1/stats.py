# api/v1/stats.py

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import datetime

# Імпортуємо сервіси
from api.deps import get_current_user
import core.firebase as firebase # Потрібен 'auth_client' для дати реєстрації
from google.cloud.firestore_v1.base_query import FieldFilter

router = APIRouter()

# Модель, яку ми повернемо фронтенду
class UserStats(BaseModel):
    chat_questions: int
    calculations: int
    days_in_system: int

@router.get("/", response_model=UserStats)
def get_user_stats(
    current_user: dict = Depends(get_current_user)
):
    """
    Збирає та повертає статистику для поточного користувача.
    """
    user_uid = current_user.get("uid")
    
    try:
        # --- 1. Запитань в чаті ---
        # Рахуємо повідомлення, де sender == 'user'
        db = firebase.ensure_initialized()
        chat_query = db.collection("messages") \
            .where(filter=FieldFilter("user_uid", "==", user_uid)) \
            .where(filter=FieldFilter("sender", "==", "user")) \
            .count() # .count() - це ефективний спосіб порахувати
            
        chat_count = chat_query.get()[0][0].value

        # --- 2. Розрахунків ---
        # Ми не зберігаємо "розрахунки", але ми зберігаємо "доходи".
        # Давайте використаємо кількість доданих доходів як показник "активності".
        income_query = db.collection("incomes") \
            .where(filter=FieldFilter("user_uid", "==", user_uid)) \
            .count()
            
        income_count = income_query.get()[0][0].value

        # --- 3. Днів в системі ---
        # Отримуємо дату реєстрації користувача з Firebase Auth
        user_record = firebase.auth_client.get_user(user_uid)
        
        # timestamp в мілісекундах, конвертуємо в секунди
        creation_timestamp_ms = user_record.user_metadata.creation_timestamp
        created_at = datetime.datetime.fromtimestamp(
            creation_timestamp_ms / 1000, 
            tz=datetime.timezone.utc
        )
        
        now = datetime.datetime.now(datetime.timezone.utc)
        days_count = (now - created_at).days
        
        return UserStats(
            chat_questions=chat_count,
            calculations=income_count, # Використовуємо кількість доходів
            days_in_system=days_count
        )

    except Exception as e:
        print(f"Помилка при зборі статистики: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не вдалося завантажити статистику: {e}"
        )
