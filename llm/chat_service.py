# llm/chat_service.py

import google.generativeai as genai
from core.config import settings
import json


try:

    genai.configure(api_key=settings.GEMINI_API_KEY)

    model = genai.GenerativeModel(model_name="gemini-2.5-flash-preview-09-2025")

except Exception as e:

    print(f"ПОМИЛКА ІНІЦІАЛІЗАЦІЇ GEMINI: {e}")

    model = None

async def get_gemini_response(user_message: str, user_context: str) -> str:
    """
    Генерує відповідь від Gemini, враховуючи контекст користувача.
    """
    
    # Це наш "системний промпт". Він каже боту, ким він має бути.
    # Ми додаємо в нього user_context, який отримали з бази даних.
    system_prompt = f"""
Ти — FOPilot, помічник для ФОП. Відповідай коротко (1–3 речення), тільки по суті запиту.
Не повторюй контекст користувача і не дублюй його питання.

Контекст користувача:
{user_context}

Правила:
- Мова: українська.
- Тільки plain text, без Markdown/LaTeX.
- Якщо запит про розрахунок/процедуру — дай стислий алгоритм у кількох пунктах.
- Якщо це не по темі ФОП — ввічливо відмовся.
    """
    
    try:
        # Ми створюємо новий чат з системним промптом
        chat_session = model.start_chat(
            history=[
                {"role": "user", "parts": [system_prompt]},
                {"role": "model", "parts": ["Добре, я FOPilot. Я готовий допомогти цьому користувачу з урахуванням його контексту."]}
            ]
        )
        
        # Надсилаємо реальне повідомлення користувача
        response = await chat_session.send_message_async(user_message)
        
        return response.text
        
    except Exception as e:
        print(f"Помилка під час виклику Gemini API: {e}")
        return "Вибачте, сталася помилка під час обробки вашого запиту до ШІ."


async def detect_intent(user_message: str) -> dict | None:
    """
    Питає модель про структуру команди і повертає JSON з intent + полями.
    Очікувані intent:
      - add_income {amount, currency?, date?, description?}
      - add_expense {amount, currency?, date?, description?}
      - create_declaration {year, quarter}
    """
    if not model:
        return None
    prompt = f"""
Визнач команду користувача. Поверни ТІЛЬКИ JSON без пояснень.
intent: add_income | add_expense | create_declaration | none
add_income/add_expense: amount (number), currency (UAH якщо не вказано), date (YYYY-MM-DD або ""), description.
create_declaration: year (number), quarter (1..4).
Якщо нічого з цього не підходить — intent: "none".
Повідомлення: "{user_message}"
"""
    try:
        resp = await model.generate_content_async(prompt)
        text = resp.text if hasattr(resp, "text") else ""
        text = text.strip().strip("`")
        # інколи модель обгортає json в ```json ... ```
        if text.startswith("json"):
            text = text[4:]
        parsed = json.loads(text)
        return parsed
    except Exception as e:
        print(f"detect_intent parse failed: {e}")
        return None
