from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException, status
from google.cloud.firestore_v1.base_query import FieldFilter

from core.firebase import ensure_initialized
from services import auth_service


def _quarter_date_range(year: int, quarter: int) -> tuple[datetime, datetime]:
    if quarter not in {1, 2, 3, 4}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Квартал має бути в діапазоні 1..4",
        )

    start_month = (quarter - 1) * 3 + 1
    start = datetime(year, start_month, 1)
    # Початок наступного кварталу (не включно)
    if start_month == 10:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, start_month + 3, 1)
    return start, end


def _to_money(value: float | int | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def get_totals_for_quarter(user_uid: str, year: int, quarter: int) -> dict:
    """
    Повертає суму доходів за квартал та розрахований ЄП.
    """
    try:
        db = ensure_initialized()
    except Exception as e:
        print(f"Не вдалося ініціалізувати Firestore, повертаю 0: {e}")
        return {"total_income": Decimal("0.00"), "single_tax": Decimal("0.00")}

    start, end = _quarter_date_range(year, quarter)

    try:
        income_query = (
            db.collection("incomes")
            .where(filter=FieldFilter("user_uid", "==", user_uid))
            .stream()
        )
    except Exception as e:
        # Якщо Firestore недоступний, повертаємо нулі, щоб не падати
        print(f"Не вдалося отримати доходи, повертаю 0: {e}")
        return {"total_income": Decimal("0.00"), "single_tax": Decimal("0.00")}

    total_income = Decimal("0.00")
    for doc in income_query:
        amount = doc.to_dict().get("amount", 0)
        date_val = doc.to_dict().get("date")
        if isinstance(date_val, datetime):
            # Приводимо таймзону до naive, щоб уникнути порівняння aware/naive
            if date_val.tzinfo:
                date_val = date_val.replace(tzinfo=None)
            if not (start <= date_val < end):
                continue
        total_income += _to_money(amount)

    profile = auth_service.get_user_profile(user_uid)
    tax_rate = Decimal(str(profile.tax_rate)) if profile and profile.tax_rate else Decimal("0.05")
    single_tax = (total_income * tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "total_income": total_income,
        "single_tax": single_tax,
    }
