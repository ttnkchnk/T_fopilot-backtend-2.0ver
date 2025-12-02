# services/declaration_service.py
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping

from services import auth_service
from core.templates import TEMPLATES_DIR
from core.templates import env as templates_env
from services.pdf_service import PDFService
from services.document_service import DocumentService  # твой локальный сторидж


def _format_money(value: float | Decimal) -> str:
    if value is None:
        value = 0
    try:
        dec = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        dec = Decimal("0.00")
    return dec.to_eng_string()


def _build_full_name(profile) -> str:
    if not profile:
        return ""
    parts = [profile.last_name, profile.first_name, profile.middle_name]
    return " ".join(p for p in parts if p)


def _extract_tax_id(profile) -> str | None:
    if not profile or not profile.onboarding_data:
        return None
    return profile.onboarding_data.get("taxId")


def build_declaration_3_defaults(
    user_uid: str,
    year: int,
    quarter: int,
    totals: Mapping[str, Any],
) -> dict:
    """
    Готує дефолтні дані для декларації 3 групи, підтягує ПІБ/ІПН з профілю.
    """
    try:
        profile = auth_service.get_user_profile(user_uid)
    except Exception as e:
        print(f"Не вдалося отримати профіль користувача {user_uid}: {e}")
        profile = None
    quarter_map = {1: "I квартал", 2: "II квартал", 3: "III квартал", 4: "IV квартал"}
    period_text = f"{quarter_map.get(quarter, '')} {year}"

    return {
        "year": year,
        "quarter": quarter,
        "period_text": period_text,
        "full_name": _build_full_name(profile),
        "tax_id": _extract_tax_id(profile),
        "total_income": float(totals.get("total_income", 0)),
        "single_tax": float(totals.get("single_tax", 0)),
        "filled_date": datetime.now().strftime("%d.%m.%Y"),
    }


def merge_declaration_overrides(base: dict, overrides: Mapping[str, Any] | None) -> dict:
    if not overrides:
        return base
    merged = base.copy()
    for key, value in overrides.items():
        if value is not None:
            merged[key] = value
    return merged


async def generate_declaration_3_pdf(user_uid: str, form_data: Mapping[str, Any]) -> dict:
    """
    Приймає готові дані для декларації (можуть бути відредаговані користувачем) і зберігає PDF.
    """
    template = templates_env.get_template("declaration_3_group.html")
    form_context = {
        "full_name": form_data.get("full_name", ""),
        "tax_id": form_data.get("tax_id", ""),
        "year": form_data.get("year"),
        "quarter": form_data.get("quarter"),
        "quarter_text": form_data.get("period_text", ""),
        "total_income": _format_money(form_data.get("total_income", 0)),
        "single_tax": _format_money(form_data.get("single_tax", 0)),
        "filled_date": form_data.get("filled_date", datetime.now().strftime("%d.%m.%Y")),
    }

    # Завжди використовуємо плаский рендер (Pillow), щоб не залежати від WeasyPrint
    pdf_bytes = PDFService.render_declaration_flat(form_context)
    year = form_data.get("year")
    quarter = form_data.get("quarter")
    filename = f"declaration_3_group_{year}_Q{quarter}.pdf"

    meta = DocumentService.save_user_document(
        user_id=user_uid,
        doc_type="declaration",
        pdf_bytes=pdf_bytes,
        filename=filename,
        extra_meta={"year": year, "quarter": quarter},
    )

    return meta
