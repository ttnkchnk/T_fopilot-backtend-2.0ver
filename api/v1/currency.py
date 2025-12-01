from fastapi import APIRouter, HTTPException
from services.monobank import get_exchange_rate

router = APIRouter(tags=["Currency"])


@router.get("/rates")
async def get_rates():
    """
    Повертає актуальні курси USD та EUR до UAH.
    """
    try:
        usd = await get_exchange_rate("USD")
        eur = await get_exchange_rate("EUR")
        return {"USD": usd, "EUR": eur, "UAH": 1.0}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Не вдалося отримати курси: {e}")
