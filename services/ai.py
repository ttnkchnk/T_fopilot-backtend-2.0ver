# core/ai.py
from typing import Literal, Sequence
import json
import re

import anyio
from google import generativeai as genai

from core.config import settings

# Настраиваем SDK один раз
genai.configure(api_key=settings.GEMINI_API_KEY)

# Можно вынести названия моделей в конфиг, но пока так
ModelName = Literal["gemini-1.5-flash", "gemini-1.5-pro"]


def _get_model(model: ModelName = "gemini-1.5-flash"):
    return genai.GenerativeModel(model)


async def generate_text(prompt: str, model: ModelName = "gemini-1.5-flash") -> str:
    """
    Базовый метод: на вход строка → на выход текст.
    Все остальные фичи (подсказки, расчёты, анализ) уже строятся сверху.
    """

    def _call():
        mdl = _get_model(model)
        resp = mdl.generate_content(prompt)
        return resp.text

    # Gemini-SDK синхронный → выносим в отдельный поток
    return await anyio.to_thread.run_sync(_call)


async def check_declaration_with_ai(
    declaration_rows: Sequence[dict],
    user_label: str | None = None,
) -> dict:
    """
    Використовує Gemini для швидкої перевірки декларації.
    Повертає словник з ключами: is_valid (bool), issues (list[str]), suggestions (list[str]).
    """
    rows_text = "\n".join(
        f"{row.get('code')}: {row.get('label')} = {row.get('value')}"
        for row in declaration_rows
    )

    user_info = f"Користувач: {user_label}" if user_label else "Користувач: (анонім)"

    prompt = f"""
Ти — податковий консультант для ФОП 3-ї групи. Перевір шаблон декларації за даними нижче.
{user_info}

Дані декларації (код: назва = значення):
{rows_text}

Перевірки, які потрібно зробити:
- Поле "02" (ІПН) має містити 10 цифр.
- Сума доходів 10 + 11 ≈ 12.
- Сума ЄП (код 21) ≈ поле 12 * (ставка коду 20 у %) / 100.
- Сума до сплати (код 40) ≈ 21 + 30 + 31.
- Перевір, що обов'язкові поля не порожні.

Формат відповіді — ТІЛЬКИ JSON без додаткового тексту:
{{
  "is_valid": true або false,
  "issues": ["перелік проблем українською"],
  "suggestions": ["лаконічні поради українською"]
}}
    """.strip()

    raw_response = await generate_text(prompt)

    def _parse_response(text: str) -> dict:
        """
        Стандартизуємо відповідь AI у словник зі строгими ключами.
        """
        try:
            json_text_match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            json_text = json_text_match.group(0) if json_text_match else text
            data = json.loads(json_text)
        except Exception:
            # Фолбек: якщо JSON не розпізнається, віддаємо загальне повідомлення
            return {
                "is_valid": False,
                "issues": ["AI не зміг сформувати структуровану відповідь"],
                "suggestions": ["Спробуйте ще раз або перевірте поля вручну"],
            }

        return {
            "is_valid": bool(data.get("is_valid", False)),
            "issues": [str(i) for i in data.get("issues", [])] if isinstance(data.get("issues"), list) else [],
            "suggestions": [str(s) for s in data.get("suggestions", [])] if isinstance(data.get("suggestions"), list) else [],
        }

    return _parse_response(raw_response)
