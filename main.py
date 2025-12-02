import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import Database
from services.scheduler import start_scheduler, scheduler
from core.firebase import initialize_firebase
from core.config import settings
from api.v1 import auth, taxes, chat, income, stats, expenses, documents, clients, currency, forms, calendar, legal_admin, legal


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_firebase()
    Database.initialize()
    start_scheduler()
    yield
    if scheduler:
        scheduler.shutdown()


app = FastAPI(title="FOPilot v2", lifespan=lifespan)

# Налаштування CORS (щоб фронтенд мав доступ)
origins = [o.strip() for o in settings.FRONTEND_ORIGIN.split(",") if o.strip()] or [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Папка для файлів (замість платного Firebase)
os.makedirs("uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="uploads"), name="static")

# --- ПІДКЛЮЧЕННЯ РОУТЕРІВ ---
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(taxes.router, prefix="/api/v1/taxes", tags=["Taxes"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(income.router, prefix="/api/v1/income", tags=["Income"])
app.include_router(stats.router, prefix="/api/v1/stats", tags=["Stats"])
app.include_router(expenses.router, prefix="/api/v1/expenses", tags=["Expenses"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(clients.router, prefix="/api/v1/clients", tags=["Clients"])
app.include_router(currency.router, prefix="/api/v1/currency", tags=["Currency"])
app.include_router(calendar.router, prefix="/api/v1", tags=["Calendar"])
app.include_router(forms.router, prefix="/api/v1", tags=["Forms"])
app.include_router(legal.router, prefix="/api/v1", tags=["Legal"])
app.include_router(legal_admin.router, prefix="/api/v1", tags=["Legal Admin"])


@app.get("/")
def read_root():
    return {"status": "ok", "version": "2.0.0"}
