import httpx
from datetime import datetime

# Простий кеш у пам'яті: { "USD": 41.5, "EUR": 44.2 }
_rates_cache = {}
_last_update = None


async def get_exchange_rate(currency_code: str) -> float:
    """
    Отримує курс валюти до гривні (UAH).
    Використовує кеш, щоб не спамити API Монобанку.
    """
    global _last_update

    if currency_code == "UAH":
        return 1.0

    # Якщо кеш є і він свіжий (менше 1 години) - беремо з нього
    # (Для спрощення просто перевіряємо наявність, оновлюватиме Scheduler)
    if currency_code in _rates_cache:
        return _rates_cache[currency_code]

    # Якщо кешу немає, робимо запит (фолбек)
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.monobank.ua/bank/currency")
            if response.status_code == 200:
                data = response.json()
                # ISO коди: 840 = USD, 978 = EUR, 980 = UAH
                target_iso = 840 if currency_code == "USD" else 978

                for item in data:
                    if item.get("currencyCodeA") == target_iso and item.get("currencyCodeB") == 980:
                        rate = float(item.get("rateBuy"))
                        _rates_cache[currency_code] = rate
                        return rate
    except Exception as e:
        print(f"Monobank API Error: {e}")

    # Аварійні курси, якщо Монобанк не відповідає
    return 41.5 if currency_code == "USD" else 45.0
