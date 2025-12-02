from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.deps import get_current_user, require_admin
from services.legal_ai_service import LegalAIService
from services.legal_repository import LegalRepository
from services.legal_ingest_service import LegalIngestService

router = APIRouter(prefix="/legal-admin", tags=["Legal Admin"])


class LegalInput(BaseModel):
    title: str
    source: str
    url: str
    law_date: date
    raw_text: str


@router.post("/ingest")
def ingest_legal_update(payload: LegalInput, current_user: dict = Depends(get_current_user)):
    # TODO: додати реальну перевірку admin-користувача (клейм або поле профілю)
    update = LegalAIService.classify_and_summarize(
        title=payload.title,
        text=payload.raw_text,
        source=payload.source,
        url=payload.url,
        law_date=payload.law_date,
    )
    doc_id = LegalRepository.add_update(update)
    return {"id": doc_id}


@router.post("/run-ingest")
async def run_ingest(_: dict = Depends(require_admin)):
    await LegalIngestService.ingest_feeds()
    return {"status": "ok"}
