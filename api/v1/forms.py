# api/v1/forms.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.deps import get_current_user
from services.declaration_service import (
    build_declaration_3_defaults,
    generate_declaration_3_pdf,
    merge_declaration_overrides,
)
from services.income_service import get_totals_for_quarter  # твоя логика

router = APIRouter(prefix="/forms", tags=["forms"])

class DeclarationPrefillResponse(BaseModel):
    year: int
    quarter: int
    period_text: str
    full_name: str
    tax_id: str | None = None
    total_income: float
    single_tax: float
    filled_date: str


class Declaration3GroupPayload(BaseModel):
    year: int
    quarter: int
    full_name: str | None = None
    tax_id: str | None = None
    total_income: float | None = None
    single_tax: float | None = None
    filled_date: str | None = None
    period_text: str | None = None


async def _get_prefill(uid: str, year: int, quarter: int) -> dict:
    totals = await get_totals_for_quarter(uid, year, quarter)
    return build_declaration_3_defaults(uid, year, quarter, totals)


@router.get("/declaration/3-group/prefill", response_model=DeclarationPrefillResponse)
async def get_declaration_3_group_prefill(
    year: int,
    quarter: int,
    user=Depends(get_current_user),
):
    uid = user.get("uid") if isinstance(user, dict) else getattr(user, "uid", None)
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Немає даних користувача")

    return await _get_prefill(uid, year, quarter)


@router.post("/declaration/3-group")
async def create_declaration_3_group(
    payload: Declaration3GroupPayload,
    user=Depends(get_current_user),
):
    uid = user.get("uid") if isinstance(user, dict) else getattr(user, "uid", None)
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Немає даних користувача")

    base_data = await _get_prefill(uid, payload.year, payload.quarter)
    payload_data = payload.dict(exclude_none=True)
    # Фіксуємо рік/квартал навіть якщо фронт їх не редагує
    payload_data.update({"year": payload.year, "quarter": payload.quarter})
    merged = merge_declaration_overrides(base_data, payload_data)

    meta = await generate_declaration_3_pdf(
        user_uid=uid,
        form_data=merged,
    )
    return meta
