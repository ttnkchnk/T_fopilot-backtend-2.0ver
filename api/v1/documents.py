from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import FileResponse
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import BaseModel
import base64
import re

from api.deps import get_current_user
from core.firebase import ensure_initialized
from services.ai import check_declaration_with_ai
from services.document_service import DocumentService, BASE_DIR

router = APIRouter()
bearer_optional = HTTPBearer(auto_error=False)


def resolve_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_optional),
):
    """
    Повертає користувача, якщо є Bearer, або фолбек на локального user.
    """
    if creds:
        try:
            return get_current_user(creds)  # type: ignore[arg-type]
        except Exception as e:
            print(f"Token validation failed, fallback to local: {e}")
    return {"uid": "local-dev"}


class DeclarationField(BaseModel):
    code: str
    label: str
    value: str


class DeclarationAICheckResponse(BaseModel):
    is_valid: bool
    issues: List[str]
    suggestions: List[str]


class DocumentMeta(BaseModel):
    id: str
    userId: str
    type: str
    fileName: str
    filePath: str
    createdAt: object | None = None
    year: int | None = None
    quarter: int | None = None
    category: str | None = None
    archived: bool | None = False


class DocumentUpload(BaseModel):
    file_name: str
    pdf_base64: str
    type: str = "declaration"
    year: int | None = None
    quarter: int | None = None
    category: str | None = None
    archived: bool | None = False


def _ts_to_datetime(val):
    if hasattr(val, "datetime"):
        return val.datetime()
    return val


@router.get("/", response_model=List[DocumentMeta])
async def list_documents(current_user: dict = Depends(resolve_current_user)):
    uid = current_user.get("uid")
    try:
        return DocumentService.list_user_documents(uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не вдалося отримати архів документів: {e}")


@router.post("/upload", response_model=DocumentMeta)
async def upload_document(payload: DocumentUpload, current_user: dict = Depends(resolve_current_user)):
    uid = current_user.get("uid")
    # Видаляємо префікс data URI, якщо є
    data = payload.pdf_base64
    match = re.match(r"^data:application/pdf;base64,(.+)$", data)
    if match:
        data = match.group(1)
    try:
        pdf_bytes = base64.b64decode(data)
    except Exception:
        raise HTTPException(status_code=400, detail="Невірний формат pdf_base64")

    meta = DocumentService.save_user_document(
        user_id=uid,
        doc_type=payload.type,
        pdf_bytes=pdf_bytes,
        filename=payload.file_name,
        extra_meta={
            "year": payload.year,
            "quarter": payload.quarter,
            "category": payload.category or payload.type,
            "archived": payload.archived or False,
        },
    )
    return meta


class ArchivePayload(BaseModel):
    archived: bool


@router.patch("/{doc_id}/archive", response_model=DocumentMeta)
async def toggle_archive_document(
    doc_id: str,
    payload: ArchivePayload,
    current_user: dict = Depends(resolve_current_user),
):
    uid = current_user.get("uid")
    meta = DocumentService.get_document_meta(doc_id)
    if meta.get("userId") != uid:
        raise HTTPException(status_code=403, detail="Немає доступу")

    updated = DocumentService.update_document_meta(doc_id, {"archived": payload.archived})
    return updated


@router.get("/{doc_id}/download", response_class=FileResponse)
async def download_document(doc_id: str, current_user: dict = Depends(resolve_current_user)):
    uid = current_user.get("uid")
    meta = DocumentService.get_document_meta(doc_id)
    if meta.get("userId") != uid:
        raise HTTPException(status_code=403, detail="Немає доступу")

    rel_path = meta.get("filePath")
    full_path = (BASE_DIR / rel_path).resolve() if rel_path else None
    if not full_path or not full_path.is_file():
        raise HTTPException(status_code=404, detail="Файл не знайдено")

    return FileResponse(
        path=full_path,
        media_type="application/pdf",
        filename=meta.get("fileName", "document.pdf"),
    )


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, current_user: dict = Depends(resolve_current_user)):
    uid = current_user.get("uid")
    meta = DocumentService.get_document_meta(doc_id)
    if meta.get("userId") != uid:
        raise HTTPException(status_code=403, detail="Немає доступу")

    rel_path = meta.get("filePath")
    full_path = (BASE_DIR / rel_path).resolve() if rel_path else None
    if full_path and full_path.is_file():
        full_path.unlink()

    DocumentService.delete_document(doc_id)
    return {"status": "ok"}


@router.post("/declaration/ai-check", response_model=DeclarationAICheckResponse)
async def declaration_ai_check(
    declaration: List[DeclarationField],
    current_user: dict = Depends(resolve_current_user),
):
    """
    Перевіряє заповнену декларацію ФОП за допомогою Gemini.
    """
    try:
        user_label = current_user.get("name") or current_user.get("email") or current_user.get("uid")
    except Exception:
        user_label = None

    try:
        result = await check_declaration_with_ai(declaration, user_label=user_label)
        return DeclarationAICheckResponse(**result)
    except Exception as e:
        print(f"Declaration AI check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Помилка перевірки декларації AI",
        )
