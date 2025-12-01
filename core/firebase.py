# Ініціалізація сервісів Firebase Admin.
import firebase_admin
from firebase_admin import credentials, auth, firestore
from core.config import settings  # 1. Ми імпортуємо налаштування

db = None
auth_client = None


def initialize_firebase():
    global db, auth_client, storage_bucket
    if not firebase_admin._apps:
        cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH)
        firebase_admin.initialize_app(cred)

    db = firestore.client()
    auth_client = auth


def ensure_initialized():
    if db is None or auth_client is None:
        initialize_firebase()
    return db
