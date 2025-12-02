import json
from datetime import date, datetime
from typing import Tuple

import google.generativeai as genai
import re

from core.config import settings
from models.legal import LegalUpdate

genai.configure(api_key=settings.GEMINI_API_KEY)
# Безпечна модель для v1beta клієнта
model = genai.GenerativeModel("gemini-2.5-flash-preview-09-2025")


CLASSIFY_PROMPT = """
Ти помічник-бухгалтер для українських ФОПів.

Ось текст змін у законодавстві (офіційне джерело):

\"\"\"{text}\"\"\"


1) Визнач чи стосуються ці зміни фізичних осіб-підприємців (ФОП). 
2) Якщо так — яких груп (1, 2, 3, 4)? Можна кілька.
3) Чи стосуються платників ПДВ, неплатників ПДВ чи обох?
4) Які основні теми (наприклад: "єдиний податок", "єсв", "ставка", "ліміти доходу",
   "звітність", "перевірки", "касові апарати" тощо)?
5) Оціни важливість для ФОПа: high / medium / low.

Відповідай СТРОГО в JSON формату:

{{
  "is_for_fop": true/false,
  "groups": [3],
  "vat_status": "vat" | "non_vat" | "both" | null,
  "topics": ["..."],
  "importance": "high" | "medium" | "low"
}}
"""

SUMMARY_PROMPT = """
Ти пояснюєш зміни у законодавстві українському ФОПу 3 групи без ПДВ
простими словами.

Ось текст змін:

\"\"\"{text}\"\"\"


1) Спочатку дай коротке узагальнене пояснення для всіх ФОПів (2-4 речення).
2) Потім окремо: поясни, що це означає КОНКРЕТНО для ФОП 3 групи без ПДВ.
   Якщо прямо не стосується їх — напиши, що змін саме для них немає.

Відповідь поверни в JSON:

{{
  "summary_general": "....",
  "summary_for_fop3_non_vat": "...."  // або "none"
}}
"""


class LegalAIService:
    @staticmethod
    def _safe_json_loads(text: str) -> dict:
        try:
            return json.loads(text)
        except Exception:
            return {}

    @staticmethod
    def classify_and_summarize(
        title: str,
        text: str,
        source: str,
        url: str,
        law_date: date,
    ) -> LegalUpdate:
        truncated_text = text[:8000]

        cls_resp = model.generate_content(CLASSIFY_PROMPT.format(text=truncated_text))
        cls_json = LegalAIService._safe_json_loads(cls_resp.text or "{}")

        is_for_fop = bool(cls_json.get("is_for_fop", True))
        groups = cls_json.get("groups") or []
        group = groups[0] if groups else None

        vat_status = cls_json.get("vat_status")
        if vat_status == "both":
            vat_status = None

        topics = cls_json.get("topics") or []
        importance = cls_json.get("importance") or "medium"

        sum_resp = model.generate_content(SUMMARY_PROMPT.format(text=truncated_text))
        sum_json = LegalAIService._safe_json_loads(sum_resp.text or "{}")

        summary_general = sum_json.get("summary_general")
        summary_for_fop3_non_vat = sum_json.get("summary_for_fop3_non_vat")

        def _make_short_summary(text_val: str | None) -> str | None:
            if not text_val:
                return None
            sentences = re.split(r"(?<=[.!?])\s+", text_val.strip())
            return " ".join(sentences[:2]).strip()

        summary_short = _make_short_summary(summary_general) or _make_short_summary(summary_for_fop3_non_vat)

        return LegalUpdate(
            date=law_date,
            created_at=datetime.utcnow(),
            source=source,
            title=title,
            url=url,
            raw_text=text,
            is_for_fop=is_for_fop,
            group=group,
            vat_status=vat_status,
            topics=topics,
            importance=importance,
            summary_general=summary_general,
            summary_for_fop3_non_vat=summary_for_fop3_non_vat,
            summary_short=summary_short,
        )
