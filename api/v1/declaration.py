# api/v1/declaration.py
from fastapi import APIRouter, Depends
from datetime import datetime
from core.templates import env as templates_env
from services.pdf_service import PDFService
from services.document_service import DocumentService
from api.dependencies import get_current_user
# откуда-то берём доходы
from services.income_service import get_total_income_for_period  # псевдо

router = APIRouter(prefix="/forms", tags=["forms"])

class DeclarationRequest(BaseModel):
    year: int
    quarter: int  # 1..4

@router.post("/declaration/3-group")
async def generate_declaration_3_group(
    payload: DeclarationRequest,
    user=Depends(get_current_user),
):
    year = payload.year
    quarter = payload.quarter

    # 1. считаем период
    # (упростим, ты можешь сделать нормально)
    quarter_text = f"{quarter}-й квартал {year} року"

    # 2. считаем суммы (примерная функция)
    total_income = await get_total_income_for_period(user.uid, year, quarter)
    single_tax = round(total_income * 0.05, 2)

    # 3. собираем контекст для шаблона
    full_name = user.full_name  # откуда-то из профиля
    tax_id = user.tax_id        # тоже из профиля

    template = templates_env.get_template("declaration_3_group.html")
    html = template.render(
        year=year,
        quarter_text=quarter_text,
        full_name=full_name,
        tax_id=tax_id,
        total_income=f"{total_income:.2f}",
        single_tax=f"{single_tax:.2f}",
        filled_at=datetime.now().strftime("%d.%m.%Y"),
    )

    # 4. HTML -> PDF
    pdf_bytes = PDFService.html_to_pdf(html, context={
        "full_name": full_name,
        "tax_id": tax_id,
        "period_text": quarter_text,
        "total_income": total_income,
        "single_tax": single_tax,
        "year": year,
        "quarter": quarter,
    })

    # 5. сохраняем документ
    filename = f"declaration_3_group_{year}_Q{quarter}.pdf"
    meta = DocumentService.save_user_document(
        user_id=user.uid,
        doc_type="declaration",
        pdf_bytes=pdf_bytes,
        filename=filename,
        extra_meta={
            "year": year,
            "quarter": quarter,
        },
    )

    return meta
