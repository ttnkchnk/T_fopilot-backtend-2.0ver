from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.monobank import get_exchange_rate
from services.legal_ingest_service import LegalIngestService

scheduler: AsyncIOScheduler | None = None


async def update_currency_rates():
    """Фонова задача: оновити кеш курсів валют"""
    print("Оновлення курсів валют...")
    await get_exchange_rate("USD")
    await get_exchange_rate("EUR")
    print("Курси валют оновлено.")


def start_scheduler():
    global scheduler
    if scheduler is not None:
        return

    scheduler = AsyncIOScheduler(timezone="Europe/Kiev")
    scheduler.add_job(update_currency_rates, "interval", hours=24, id="currency_update")
    scheduler.add_job(LegalIngestService.ingest_feeds, "interval", hours=24, id="legal_ingest")
    scheduler.start()
