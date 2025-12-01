# api/v1/chat.py

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List
import datetime
from google.cloud.firestore_v1.base_query import FieldFilter
# Наші сервіси для збору контексту
from services import auth_service, tax_service
from models.tax import TaxCalculationRequest
from core.firebase import ensure_initialized # Імпортуємо Firestore

# Наш оновлений chat_service
from llm.chat_service import get_gemini_response
from models.chat import ChatMessageRequest, ChatMessageResponse
from api.deps import get_current_user

router = APIRouter()

# --- Нова модель для повернення історії на фронтенд ---
class MessageHistory(BaseModel):
    id: str
    sender: str # 'user' або 'bot'
    text: str
    timestamp: datetime.datetime

# --- Ендпоінт POST (змінено, щоб ЗБЕРІГАТИ повідомлення) ---
@router.post("/", response_model=ChatMessageResponse)
async def chat_with_bot(
    request: ChatMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Надсилає повідомлення, збирає контекст, отримує відповідь
    І ЗБЕРІГАЄ обидва повідомлення в Firestore.
    """
    user_uid = current_user.get("uid")
    
    try:
        db = ensure_initialized()
        # --- ЕТАП 1: ЗБІР КОНТЕКСТУ (як і раніше) ---
        profile = auth_service.get_user_profile(user_uid)
        if not profile:
            raise HTTPException(status_code=404, detail="Профіль користувача не знайдено")

        income_query = db.collection("incomes").where(
            filter=FieldFilter("user_uid", "==", user_uid)
        ).stream()
        total_income = sum(doc.to_dict().get('amount', 0) for doc in income_query)
        
        tax_request = TaxCalculationRequest(quarterly_income=total_income)
        tax_data = tax_service.calculate_taxes(tax_request, user_uid)

        # --- ЕТАП 2: ФОРМУВАННЯ КОНТЕКСТНОГО ПРОМПТУ (як і раніше) ---
        user_context = f"""
        - Ім'я користувача: {profile.first_name}
        - Група ФОП: {profile.fop_group} група
        - Ставка податку: {profile.tax_rate * 100}%
        - Дохід за поточний квартал: {total_income:.2f} грн
        - Розрахований Єдиний Податок (ЄП): {tax_data.single_tax:.2f} грн
        - Розрахований Єдиний Соціальний Внесок (ЄСВ): {tax_data.social_contribution:.2f} грн
        - Всього податків до сплати: {tax_data.total_tax:.2f} грн
        """

        # --- ЕТАП 3: ВИКЛИК ШІ (як і раніше) ---
        reply = await get_gemini_response(request.message, user_context)
        
        # --- ЕТАП 4: ЗБЕРЕЖЕННЯ В БАЗУ ДАНИХ (НОВЕ!) ---
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        
        # 4.1 Зберігаємо повідомлення користувача
        db.collection("messages").add({
            "user_uid": user_uid,
            "sender": "user",
            "text": request.message,
            "timestamp": utc_now
        })
        
        # 4.2 Зберігаємо відповідь бота
        db.collection("messages").add({
            "user_uid": user_uid,
            "sender": "bot",
            "text": reply,
            "timestamp": utc_now + datetime.timedelta(seconds=1) # (щоб гарантувати порядок)
        })
        
        return ChatMessageResponse(reply=reply)

    except Exception as e:
        print(f"Помилка у chat_with_bot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Внутрішня помилка сервера: {e}"
        )

# --- Ендпоінт GET (НОВИЙ!, для завантаження історії) ---
@router.get("/history", response_model=List[MessageHistory])
def get_chat_history(
    current_user: dict = Depends(get_current_user)
):
    """
    Отримує всю історію чату для поточного користувача.
    """
    user_uid = current_user.get("uid")
    try:
        db = ensure_initialized()
        # ↓↓↓ ЗАПИТ ОНОВЛЕНО, ЩОБ ВИПРАВИТИ UserWarning ↓↓↓
        messages_query = db.collection("messages") \
            .where(filter=FieldFilter("user_uid", "==", user_uid)) \
            .order_by("timestamp") \
            .stream()
            
        history = []
        for msg in messages_query:
            msg_data = msg.to_dict()
            
            python_datetime = msg_data.get("timestamp") 
            
            history.append(MessageHistory(
                id=msg.id,
                sender=msg_data.get("sender"),
                text=msg_data.get("text"),
                timestamp=python_datetime # <-- Передаємо правильну змінну
            ))

            
        return history
        
    except Exception as e:
        print(f"Помилка у get_chat_history: {e}")
        raise HTTPException(status_code=500, detail="Не вдалося завантажити історію чату")
# API роутер для чату
# Зміни: 1. Імпортовано run_in_threadpool
#        2. Функція chat_with_bot стала async
#        3. Виклик get_llama_response обгорнуто в await run_in_threadpool

# from fastapi import APIRouter, Depends
# from fastapi.concurrency import run_in_threadpool
# from models.chat import ChatMessageRequest, ChatMessageResponse
# from llm.chat_service import get_llama_response
# from api.deps import get_current_user

# router = APIRouter()


# @router.post("/", response_model=ChatMessageResponse)
# async def chat_with_bot(
#         request: ChatMessageRequest,
#         current_user: dict = Depends(get_current_user)
# ):
#     """
#     Надсилає повідомлення користувача до Llama 2 та повертає відповідь.
#     AI обмежений відповідати лише на теми ФОП та податків.
#     Запит до AI виконується у фоновому потоці, щоб не блокувати сервер.
#     """
#     reply = await run_in_threadpool(get_llama_response, request.message)

#     return ChatMessageResponse(reply=reply)
