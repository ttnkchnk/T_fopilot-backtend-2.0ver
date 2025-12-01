# api/v1/expenses.py

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List
import datetime

# Імпортуємо залежності
from api.deps import get_current_user
from core.firebase import ensure_initialized
from google.cloud.firestore_v1.base_query import FieldFilter

router = APIRouter()

# --- 1. Pydantic Моделі ---
# Модель, яку ми очікуємо від фронтенду

class ExpenseCreate(BaseModel):
    amount: float
    description: str
    date: datetime.date

# Модель, яку ми повертатимемо з бази даних

class ExpenseInDB(ExpenseCreate):
    id: str
    user_uid: str

# --- 2. Ендпоінт POST (Створити витрату) ---

@router.post(
    "/", 
    response_model=ExpenseInDB, 
    status_code=status.HTTP_201_CREATED
)
def create_expense(
    expense_data: ExpenseCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Створює новий запис про витрати для поточного користувача.
    """
    user_uid = current_user.get("uid")
    
    new_expense_data = expense_data.dict()
    new_expense_data["user_uid"] = user_uid
    
    # Перетворюємо 'date' на 'datetime' для сумісності з Firestore
    new_expense_data["date"] = datetime.datetime.combine(expense_data.date, datetime.time.min)
    
    try:
        db = ensure_initialized()
        # Додаємо новий документ до колекції 'expenses'
        doc_ref = db.collection("expenses").add(new_expense_data)
        created_doc_id = doc_ref[1].id
        
        return ExpenseInDB(
            id=created_doc_id,
            user_uid=user_uid,
            **expense_data.dict()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Помилка при створенні запису: {str(e)}"
        )

# --- 3. Ендпоінт GET (Отримати всі витрати) ---

@router.get(
    "/", 
    response_model=List[ExpenseInDB]
)
def get_all_expenses(
    current_user: dict = Depends(get_current_user)
):
    """
    Отримує список усіх записів про витрати для поточного користувача.
    """
    user_uid = current_user.get("uid")
    
    try:
        db = ensure_initialized()
        # ЗАПИТ (відступ 1)
        expenses_query = db.collection("expenses") \
            .where(filter=FieldFilter("user_uid", "==", user_uid)) \
            .order_by("date", direction="DESCENDING") \
            .stream()
            
        # ЛОГІКА ОБРОБКИ
        results = []
        for doc in expenses_query:
            # ЛОГІКА ЦИКЛУ (відступ 2)
            doc_data = doc.to_dict()
            
            
            results.append(ExpenseInDB(
                id=doc.id,      
                **doc_data      
            ))
            
            
        return results
        
    except Exception as e:
        print(f"Помилка при читанні записів: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Помилка при читанні записів: {e}"
        )


@router.delete(
    "/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_expense(
    expense_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Видаляє запис про витрату поточного користувача.
    """
    user_uid = current_user.get("uid")
    try:
        doc_ref = db.collection("expenses").document(expense_id)
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
            detail=f"Помилка при видаленні витрати: {e}"
        )
