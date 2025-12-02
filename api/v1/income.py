from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List
import datetime # Використовуватимемо для дати

# Імпортуємо залежності
from api.deps import get_current_user
from core.firebase import ensure_initialized

router = APIRouter()

# --- 1. Pydantic Моделі ---
# Модель, яку ми очікуємо від фронтенду при створенні

class IncomeCreate(BaseModel):
    amount: float
    description: str
    date: datetime.date # Фронтенд може надсилати дату як рядок, FastAPI перетворить її

# Модель, яку ми повертатимемо з бази даних (включаючи ID)

class IncomeInDB(IncomeCreate):
    id: str
    user_uid: str

# --- 2. Ендпоінт POST (Створити дохід) ---

@router.post(
    "/", 
    response_model=IncomeInDB, 
    status_code=status.HTTP_201_CREATED
)
def create_income(
    income_data: IncomeCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Створює новий запис про дохід для поточного користувача.
    """
    user_uid = current_user.get("uid")
    if user_uid == "local-dev":
        return IncomeInDB(id="local-dev", user_uid=user_uid, **income_data.dict())
    
    new_income_data = income_data.dict()
    new_income_data["user_uid"] = user_uid
    
    # ↓↓↓ ОДИН НОВИЙ РЯДОК, ЯКИЙ ВСЕ ВИПРАВЛЯЄ ↓↓↓
    # Перетворюємо 'date' на 'datetime' (на північ), бо Firestore це любить
    new_income_data["date"] = datetime.datetime.combine(income_data.date, datetime.time.min)
    
    try:
        db = ensure_initialized()
        # Тепер Firestore отримає datetime і буде задоволений
        doc_ref = db.collection("incomes").add(new_income_data)
        
        created_doc_id = doc_ref[1].id
        
        return IncomeInDB(
            id=created_doc_id,
            user_uid=user_uid,
            **income_data.dict() # Pydantic коректно поверне 'date'
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Помилка при створенні запису в Firestore: {str(e)}"
        )

# --- 3. Ендпоінт GET (Отримати всі доходи) ---

@router.get(
    "/", 
    response_model=List[IncomeInDB]
)
def get_all_income(
    current_user: dict = Depends(get_current_user)
):
    """
    Отримує список усіх записів про доходи для поточного користувача.
    """
    user_uid = current_user.get("uid")
    if user_uid == "local-dev":
        return []
    
    try:
        db = ensure_initialized()
        # Шукаємо всі документи в 'incomes', де 'user_uid' збігається
        income_query = db.collection("incomes").where("user_uid", "==", user_uid).stream()
        
        results = []
        for doc in income_query:
            # Перетворюємо документ Firestore на словник
            doc_data = doc.to_dict()
            # Створюємо об'єкт IncomeInDB, додаючи ID документа
            income_entry = IncomeInDB(
                id=doc.id,
                **doc_data
            )
            results.append(income_entry)
            
        # Сортуємо за датою (новіші спочатку) - опціонально, але корисно
        results.sort(key=lambda x: x.date, reverse=True)
            
        return results
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Помилка при читанні записів з Firestore: {str(e)}"
        )


@router.delete(
    "/{income_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_income(
    income_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Видаляє запис про дохід поточного користувача.
    """
    user_uid = current_user.get("uid")
    if user_uid == "local-dev":
        return
    try:
        doc_ref = db.collection("incomes").document(income_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Запис не знайдено")

        data = doc.to_dict()
        if data.get("user_uid") != user_uid:
            raise HTTPException(status_code=403, detail="Немає доступу до запису")

        doc_ref.delete()
        return
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Помилка при видаленні доходу: {e}"
        )
