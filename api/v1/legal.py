from calendar import monthrange
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query

from api.deps import get_current_user
from services import auth_service
from services.legal_repository import LegalRepository
from fastapi import HTTPException

router = APIRouter(prefix="/legal", tags=["Legal updates"])


def month_start_end(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    last_day = monthrange(year, month)[1]
    end = date(year, month, last_day)
    return start, end


@router.get("/monthly-digest")
def get_monthly_digest(
    year: int = Query(default_factory=lambda: datetime.utcnow().year),
    month: int = Query(default_factory=lambda: datetime.utcnow().month),
    current_user: dict = Depends(get_current_user),
):
    start_date, end_date = month_start_end(year, month)

    uid = current_user.get("uid", "local-dev")
    profile = auth_service.get_user_profile(uid) if uid != "local-dev" else None

    group = getattr(profile, "fop_group", None) if profile else None
    vat_status = "vat" if getattr(profile, "is_vat_payer", False) else "non_vat"

    updates = LegalRepository.get_updates_for_period(
        start_date=start_date,
        end_date=end_date,
        group=group,
        vat_status=vat_status,
    )

    items = []
    for u in updates:
        summary = u.summary_for_fop3_non_vat or u.summary_general
        items.append(
            {
                "id": u.id,
                "date": u.date.isoformat() if isinstance(u.date, date) else str(u.date),
                "title": u.title,
                "topic": (u.topics[0] if u.topics else None),
                "importance": u.importance,
                "summary": summary,
                "source": u.source,
                "url": u.url,
            }
        )

    return {
        "year": year,
        "month": month,
        "count": len(items),
        "items": items,
    }


def quarter_start_end(year: int, quarter: int) -> tuple[date, date]:
    if quarter not in {1, 2, 3, 4}:
        raise HTTPException(status_code=400, detail="quarter must be 1..4")
    start_month = (quarter - 1) * 3 + 1
    end_month = start_month + 2
    start_date = date(year, start_month, 1)
    last_day = monthrange(year, end_month)[1]
    end_date = date(year, end_month, last_day)
    return start_date, end_date


@router.get("/digests")
def get_digests(
    period: str = Query("month", regex="^(month|quarter|year)$"),
    year: int = Query(default_factory=lambda: datetime.utcnow().year),
    month: int | None = Query(None),
    quarter: int | None = Query(None),
    importance: str | None = Query(None, regex="^(high|medium|low)$"),
    topic: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
):
    # Валідація періоду
    if year < 2000 or year > 2100:
        raise HTTPException(status_code=400, detail="invalid year")

    if period == "month":
        if month is None:
            month = datetime.utcnow().month
        if month < 1 or month > 12:
            raise HTTPException(status_code=400, detail="invalid month")
        start_date, end_date = month_start_end(year, month)
        period_label = f"{year}-{str(month).zfill(2)}"
    elif period == "quarter":
        if quarter is None:
            quarter = (datetime.utcnow().month - 1) // 3 + 1
        start_date, end_date = quarter_start_end(year, quarter)
        period_label = f"{year}-Q{quarter}"
    else:  # year
        start_date = date(year, 1, 1)
        end_date = date(year, 12, 31)
        period_label = str(year)

    uid = current_user.get("uid", "local-dev")
    profile = auth_service.get_user_profile(uid) if uid != "local-dev" else None
    group = getattr(profile, "fop_group", None) if profile else None
    vat_status = "vat" if getattr(profile, "is_vat_payer", False) else "non_vat"

    updates = LegalRepository.get_updates_for_period(
        start_date=start_date,
        end_date=end_date,
        group=group,
        vat_status=vat_status,
    )

    topic_lower = topic.lower() if topic else None
    items = []
    for u in updates:
        summary = u.summary_for_fop3_non_vat or u.summary_general
        if importance and u.importance != importance:
            continue
        if topic_lower:
            topics = [t.lower() for t in (u.topics or [])]
            haystack = " ".join(topics + [u.title.lower(), (summary or "").lower()])
            if topic_lower not in haystack:
                continue
        items.append(
            {
                "id": u.id,
                "title": u.title,
                "summary": summary,
                "summary_short": u.summary_short,
                "law_date": u.date.isoformat() if isinstance(u.date, date) else str(u.date),
                "source": u.source,
                "source_url": u.url,
                "tags": u.topics or [],
                "impact_level": u.importance,
            }
        )

    scope = f"fop_group{group}_non_vat" if group else "fop_non_vat"
    return {
        "period": period_label,
        "scope": scope,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "items": items,
    }
