from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.monobank import get_exchange_rate

scheduler = AsyncIOScheduler()


async def update_currency_rates():
    """Фонова задача: оновити кеш курсів валют"""
    print("Оновлення курсів валют...")
    await get_exchange_rate("USD")
    await get_exchange_rate("EUR")
    print("Курси валют оновлено.")


def start_scheduler():
    # Запускаємо задачу раз на 60 хвилин
    scheduler.add_job(update_currency_rates, 'interval', minutes=60)
    scheduler.start()
