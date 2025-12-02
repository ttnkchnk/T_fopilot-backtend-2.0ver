# services/document_service.py
from pathlib import Path
from uuid import uuid4
from typing import Literal
from firebase_admin import firestore
from fastapi import HTTPException
import json
from datetime import datetime

from core.firebase import ensure_initialized

BASE_DIR = Path(__file__).resolve().parent.parent
DOCUMENTS_DIR = BASE_DIR / "storage" / "documents"
LOCAL_INDEX = DOCUMENTS_DIR / "index.json"


def _db():
    return ensure_initialized()


def _load_local_index() -> list[dict]:
    if LOCAL_INDEX.is_file():
        try:
            return json.loads(LOCAL_INDEX.read_text())
        except Exception:
            return []
    return []


def _save_local_index(items: list[dict]) -> None:
    LOCAL_INDEX.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_INDEX.write_text(json.dumps(items, ensure_ascii=False, indent=2))


DocumentType = Literal["declaration", "invoice", "other"]


class DocumentService:
    @staticmethod
    def _save_meta_firestore(meta: dict) -> None:
        # Тимчасово пропускаємо запис у Firestore, щоб не блокувало без зовнішніх залежностей/мережі
        return

    @staticmethod
    def _append_local_meta(meta: dict) -> None:
        items = _load_local_index()
        items = [m for m in items if m.get("id") != meta["id"]]
        items.append(meta)
        _save_local_index(items)

    @staticmethod
    def save_user_document(
        user_id: str,
        doc_type: DocumentType,
        pdf_bytes: bytes,
        filename: str,
        extra_meta: dict | None = None,
    ) -> dict:
        doc_id = str(uuid4())

        user_dir = DOCUMENTS_DIR / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        full_path = user_dir / filename
        full_path.write_bytes(pdf_bytes)

        created_at = datetime.utcnow().isoformat()
        meta = {
            "id": doc_id,
            "userId": user_id,
            "type": doc_type,
            "fileName": filename,
            "filePath": str(full_path.relative_to(BASE_DIR)),
            "createdAt": created_at,
        }
        if extra_meta:
            meta.update(extra_meta)

        DocumentService._save_meta_firestore(meta)
        DocumentService._append_local_meta(meta)
        return meta

    @staticmethod
    def get_document_meta(doc_id: str) -> dict:
        try:
            doc = _db().collection("documents").document(doc_id).get()
            if doc.exists:
                return doc.to_dict()
        except Exception as e:
            print(f"Firestore недоступний у get_document_meta: {e}")

        items = _load_local_index()
        for item in items:
            if item.get("id") == doc_id:
                return item
        raise HTTPException(status_code=404, detail="Документ не знайдено")

    @staticmethod
    def list_user_documents(user_id: str) -> list[dict]:
        docs: list[dict] = []
        try:
            fs_docs = (
                _db()
                .collection("documents")
                .where("userId", "==", user_id)
                .stream()
            )
            docs = [d.to_dict() for d in fs_docs]
        except Exception as e:
            print(f"Firestore недоступний у list_user_documents: {e}")

        local_docs = [d for d in _load_local_index() if d.get("userId") == user_id]
        seen = {d.get("id") for d in docs}
        for d in local_docs:
            if d.get("id") not in seen:
                docs.append(d)

        def _ts(val):
            if hasattr(val, "datetime"):
                return val.datetime()
            if isinstance(val, str):
                try:
                    return datetime.fromisoformat(val)
                except Exception:
                    return 0
            return val or 0

        docs.sort(key=lambda d: _ts(d.get("createdAt")), reverse=True)
        return docs

    @staticmethod
    def update_document_meta(doc_id: str, updates: dict) -> dict:
        # Firestore (best effort)
        try:
            _db().collection("documents").document(doc_id).update(updates)
        except Exception as e:
            print(f"Firestore недоступний у update_document_meta: {e}")

        # Локальний індекс
        items = _load_local_index()
        updated = None
        for item in items:
            if item.get("id") == doc_id:
                item.update(updates)
                updated = item
                break
        if updated:
            _save_local_index(items)
            return updated
        raise HTTPException(status_code=404, detail="Документ не знайдено")

    @staticmethod
    def delete_document(doc_id: str) -> None:
        # Firestore (best effort)
        try:
            _db().collection("documents").document(doc_id).delete()
        except Exception as e:
            print(f"Firestore недоступний у delete_document: {e}")

        items = _load_local_index()
        filtered = [i for i in items if i.get("id") != doc_id]
        _save_local_index(filtered)
