from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class LegalUpdate(BaseModel):
    id: Optional[str] = None
    date: date
    created_at: datetime = Field(default_factory=datetime.utcnow)

    source: str
    title: str
    url: str

    raw_text: str

    is_for_fop: bool = True
    group: Optional[int] = None
    vat_status: Optional[str] = None  # "vat", "non_vat", None
    topics: List[str] = Field(default_factory=list)
    importance: str = "medium"

    summary_general: Optional[str] = None
    summary_for_fop3_non_vat: Optional[str] = None
    summary_short: Optional[str] = None
