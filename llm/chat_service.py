# llm/chat_service.py

import google.generativeai as genai
from core.config import settings


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
    Ти — FOPilot, корисний ШІ-помічник для українських ФОП.
    Твоя місія — чітко і професійно відповідати на питання, пов'язані з веденням ФОП.
    
    ВАЖЛИВО: Ти спілкуєшся з конкретним користувачем. Ось його контекст,
    який ти МАЄШ використовувати для надання персоналізованих відповідей:
    ---
    {user_context}
    ---
    
    Завжди відповідай українською мовою.
    Відповідай виключно звичайним текстом (plain text).

ЗАБОРОНЕНО використовувати Markdown форматування (ніяких зірочок ** для жирного шрифту, ніяких _ для курсиву, ніяких заголовків #).

ЗАБОРОНЕНО використовувати LaTeX або математичні формули (ніяких $$, \frac, \text).

Пиши суми та розрахунки у простому зрозумілому форматі (наприклад: '134 000 / 3 = 44 666.67 грн').

Не використовуй таблиці, використовуй прості списки.
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



