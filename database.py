import firebase_admin
from firebase_admin import credentials, firestore, storage
from config import settings

class Database:
    _db = None
    _bucket = None

    @classmethod
    def initialize(cls):
        if not firebase_admin._apps:
            cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH)
            bucket_name = getattr(settings, "FIREBASE_STORAGE_BUCKET", None)
            if bucket_name:
                firebase_admin.initialize_app(cred, {"storageBucket": bucket_name})
            else:
                firebase_admin.initialize_app(cred)
            cls._db = firestore.client()
            cls._bucket = storage.bucket() if bucket_name else None
            print("Firebase Firestore & Storage connected!")

    @classmethod
    def get_db(cls):
        if cls._db is None:
            cls.initialize()
        return cls._db

    @classmethod
    def get_bucket(cls):
        if cls._bucket is None:
            cls.initialize()
        return cls._bucket

# Dependency helper

def get_db():
    return Database.get_db()
