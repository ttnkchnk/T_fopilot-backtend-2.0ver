from datetime import date
from fastapi import APIRouter

from services.calendar_service import TaxCalendarService

router = APIRouter(prefix="/calendar", tags=["Calendar"])


@router.get("/")
def get_calendar(year: int = date.today().year):
    return {
        "ep": TaxCalendarService.get_monthly_ep_deadlines(year),
        "esv": TaxCalendarService.get_quarterly_esv_deadlines(year),
        "declaration": TaxCalendarService.get_declaration_deadlines(year),
    }
