from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    model_config = ConfigDict(extra="ignore", env_file=".env")

    FIREBASE_SERVICE_ACCOUNT_KEY_PATH: str
    FIREBASE_STORAGE_BUCKET: str | None = None
    MONOBANK_API_TOKEN: str
    MONOBANK_API_URL: str
    GEMINI_API_KEY: str | None = None
    FRONTEND_ORIGIN: str
    MIN_SOCIAL_CONTRIBUTION_MONTHLY: float = 1760.00

settings = Settings()

