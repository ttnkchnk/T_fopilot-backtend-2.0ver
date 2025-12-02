# api/v1/documents_local.py
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from services.document_service import DocumentService, BASE_DIR
from api.dependencies import get_current_user
from pathlib import Path
from firebase_admin import firestore

router = APIRouter(prefix="/documents", tags=["documents"])
db = firestore.client()

@router.get("/")
async def list_documents(user=Depends(get_current_user)):
    docs = (
        db.collection("documents")
        .where("userId", "==", user.uid)
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .stream()
    )
    return [d.to_dict() for d in docs]

@router.get("/{doc_id}/download", response_class=FileResponse)
async def download_document(doc_id: str, user=Depends(get_current_user)):
    meta = DocumentService.get_document_meta(doc_id)
    if meta["userId"] != user.uid:
        raise HTTPException(status_code=403, detail="Немає доступу")

    rel_path = meta["filePath"]
    full_path = (BASE_DIR / rel_path).resolve()
    if not full_path.is_file():
        raise HTTPException(status_code=404, detail="Файл не знайдено")

    return FileResponse(
        path=full_path,
        media_type="application/pdf",
        filename=meta.get("fileName", "document.pdf"),
    )

@router.delete("/{doc_id}")
async def delete_document(doc_id: str, user=Depends(get_current_user)):
    meta = DocumentService.get_document_meta(doc_id)
    if meta["userId"] != user.uid:
        raise HTTPException(status_code=403, detail="Немає доступу")

    rel_path = meta["filePath"]
    full_path = (BASE_DIR / rel_path).resolve()
    if full_path.is_file():
        full_path.unlink()

    db.collection("documents").document(doc_id).delete()
    return {"status": "ok"}
