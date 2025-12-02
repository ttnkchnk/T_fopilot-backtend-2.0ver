# api/v1/chat.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from typing import List
import datetime
from google.cloud.firestore_v1.base_query import FieldFilter
from types import SimpleNamespace
# Наші сервіси для збору контексту
from services import auth_service, tax_service
from models.tax import TaxCalculationRequest
from core.firebase import ensure_initialized # Імпортуємо Firestore

# Наш оновлений chat_service
from llm.chat_service import get_gemini_response, detect_intent
from models.chat import ChatMessageRequest, ChatMessageResponse
from api.deps import get_current_user

router = APIRouter()
bearer_optional = HTTPBearer(auto_error=False)


def resolve_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_optional),
):
    """
    Дозволяє працювати без токена у локальній розробці.
    """
    if creds:
        # Якщо токен є, але він невалідний — хай підніметься 401, щоб фронт оновив сесію
        return get_current_user(creds)  # type: ignore[arg-type]
    return {"uid": "local-dev"}

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
    current_user: dict = Depends(resolve_current_user)
):
    """
    Надсилає повідомлення, збирає контекст, отримує відповідь
    І ЗБЕРІГАЄ обидва повідомлення в Firestore.
    """
    user_uid = current_user.get("uid")
    
    try:
        db = ensure_initialized() if user_uid != "local-dev" else None
        # --- ЕТАП 1: ЗБІР КОНТЕКСТУ (як і раніше) ---
        if user_uid == "local-dev":
            profile = SimpleNamespace(first_name="Local User", fop_group=3, tax_rate=0.05)
            total_income = 0
        else:
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

        # --- ЕТАП 3: Спроба розпізнати команду ---
        intent_data = await detect_intent(request.message)
        reply = None

        # Швидкий парсер для декларації без LLM
        def simple_parse_decl(message: str):
            low = message.lower()
            if "декларац" not in low:
                return None
            import re
            q_match = re.search(r"(?:квартал|квартал[^\d]{0,3})([1-4])", low)
            y_match = re.search(r"(20\d{2})", low)
            return {
                "intent": "create_declaration",
                "quarter": int(q_match.group(1)) if q_match else None,
                "year": int(y_match.group(1)) if y_match else None,
            }

        quick_decl = simple_parse_decl(request.message)
        if not intent_data or intent_data.get("intent") == "none":
            if quick_decl:
                intent_data = quick_decl

        # Простий хардкодований фолбек, якщо модель не впоралася
        if (not intent_data) or intent_data.get("intent") == "none":
            low = request.message.lower()
            if "додай дохід" in low or "добавь доход" in low:
                intent_data = {"intent": "add_income"}
            if "витрат" in low or "расход" in low:
                intent_data = {"intent": "add_expense"}
            if "декларац" in low:
                # спробуємо витягти квартал/рік
                import re
                q = re.search(r"(1|2|3|4)", low)
                yr = re.search(r"(20\\d{2})", low)
                intent_data = {
                    "intent": "create_declaration",
                    "quarter": int(q.group(1)) if q else None,
                    "year": int(yr.group(1)) if yr else None,
                }

        try:
            async def add_income_intent(data: dict) -> str:
                amount = float(data.get("amount") or 0)
                if amount <= 0:
                    return "Не вдалося додати дохід: сума не вказана."
                desc = data.get("description") or "Дохід"
                date_raw = data.get("date")
                if date_raw:
                    try:
                        dt = datetime.datetime.fromisoformat(date_raw)
                    except Exception:
                        dt = datetime.datetime.now()
                else:
                    dt = datetime.datetime.now()
                db.collection("incomes").add({
                    "amount": amount,
                    "description": desc,
                    "date": dt,
                    "user_uid": user_uid,
                })
                return f"Додала дохід {amount:.2f} грн ({desc}) на дату {dt.date()}. Він вже у розділі доходів."

            async def add_expense_intent(data: dict) -> str:
                amount = float(data.get("amount") or 0)
                if amount <= 0:
                    return "Не вдалося додати витрату: сума не вказана."
                desc = data.get("description") or "Витрата"
                date_raw = data.get("date")
                if date_raw:
                    try:
                        dt = datetime.datetime.fromisoformat(date_raw)
                    except Exception:
                        dt = datetime.datetime.now()
                else:
                    dt = datetime.datetime.now()
                db.collection("expenses").add({
                    "amount": amount,
                    "description": desc,
                    "date": dt,
                    "user_uid": user_uid,
                })
                return f"Додала витрату {amount:.2f} грн ({desc}) на дату {dt.date()}. Запис збережено."

            async def create_declaration_intent(data: dict) -> str:
                year = int(data.get("year") or datetime.datetime.now().year)
                quarter = int(data.get("quarter") or 1)
                from services.income_service import get_totals_for_quarter
                from services.declaration_service import build_declaration_3_defaults, merge_declaration_overrides, generate_declaration_3_pdf

                totals = await get_totals_for_quarter(user_uid, year, quarter)
                base = build_declaration_3_defaults(user_uid, year, quarter, totals)
                merged = merge_declaration_overrides(base, {"year": year, "quarter": quarter})
                meta = await generate_declaration_3_pdf(user_uid=user_uid, form_data=merged)
                return f"Згенерувала декларацію за {quarter}-й квартал {year}. Файл: {meta.get('fileName')} (архів документів)."

            if intent_data and intent_data.get("intent") in {"add_income", "add_expense", "create_declaration"}:
                intent = intent_data.get("intent")
                if intent == "add_income":
                    reply = await add_income_intent(intent_data)
                elif intent == "add_expense":
                    reply = await add_expense_intent(intent_data)
                elif intent == "create_declaration":
                    try:
                        reply = await create_declaration_intent(intent_data)
                    except Exception as decl_err:
                        print(f"Declaration intent failed: {decl_err}")
                        reply = "Не вдалося згенерувати декларацію. Спробуйте уточнити квартал/рік."
        except Exception as intent_err:
            print(f"Intent handling failed: {intent_err}")
            reply = None

        # --- ЕТАП 4: Якщо немає команди — звичайна відповідь ---
        if reply is None:
            reply = await get_gemini_response(request.message, user_context)
        
        # --- ЕТАП 4: ЗБЕРЕЖЕННЯ В БАЗУ ДАНИХ (НОВЕ!) ---
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        
        # 4.1 Зберігаємо повідомлення користувача
        if db:
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
    current_user: dict = Depends(resolve_current_user)
):
    """
    Отримує всю історію чату для поточного користувача.
    """
    user_uid = current_user.get("uid")
    try:
        if user_uid == "local-dev":
            return []
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
