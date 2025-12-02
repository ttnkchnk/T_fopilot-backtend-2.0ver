from datetime import date
from typing import List, Optional
from google.cloud.firestore_v1.base_query import FieldFilter

from core.firebase import ensure_initialized
from models.legal import LegalUpdate

COLLECTION = "legal_updates"


class LegalRepository:
    @staticmethod
    def add_update(update: LegalUpdate) -> str:
        db = ensure_initialized()
        data = update.model_dump(exclude={"id"})
        data["date"] = update.date.isoformat()
        data["created_at"] = update.created_at.isoformat()

        _, doc_ref = db.collection(COLLECTION).add(data)
        return doc_ref.id

    @staticmethod
    def get_updates_for_period(
        start_date: date,
        end_date: date,
        group: Optional[int],
        vat_status: Optional[str],
    ) -> List[LegalUpdate]:
        db = ensure_initialized()

        # Мінімальний запит без складних композитних індексів: діапазон дат + прапор ФОП.
        base_query = (
            db.collection(COLLECTION)
            .where(filter=FieldFilter("date", ">=", start_date.isoformat()))
            .where(filter=FieldFilter("date", "<=", end_date.isoformat()))
            .where(filter=FieldFilter("is_for_fop", "==", True))
        )

        results: list[LegalUpdate] = []
        for doc in base_query.stream():
            data = doc.to_dict()
            data["id"] = doc.id
            candidate = LegalUpdate(**data)

            # Локальна фільтрація по групі та ПДВ, щоб не вимагати складних індексів.
            if group is not None:
                if candidate.group is not None and candidate.group != group:
                    continue
            if vat_status is not None:
                if candidate.vat_status is not None and candidate.vat_status != vat_status:
                    continue

            results.append(candidate)

        return results

    @staticmethod
    def exists_by_url(url: str) -> bool:
        db = ensure_initialized()
        docs = list(db.collection(COLLECTION).where(filter=FieldFilter("url", "==", url)).limit(1).stream())
        return len(docs) > 0

    @staticmethod
    def upsert_by_url(update: LegalUpdate) -> str:
        """
        Якщо документ з таким url існує — оновлюємо його полями update.
        Інакше створюємо новий.
        """
        db = ensure_initialized()
        docs = list(db.collection(COLLECTION).where(filter=FieldFilter("url", "==", update.url)).limit(1).stream())
        data = update.model_dump(exclude={"id"})
        data["date"] = update.date.isoformat()
        data["created_at"] = update.created_at.isoformat()

        if docs:
            doc_ref = docs[0].reference
            doc_ref.set(data)
            return doc_ref.id
        else:
            _, doc_ref = db.collection(COLLECTION).add(data)
            return doc_ref.id
