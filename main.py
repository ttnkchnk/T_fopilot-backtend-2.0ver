import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import Database
from services.scheduler import start_scheduler
from core.firebase import initialize_firebase
from api.v1 import auth, taxes, chat, income, stats, expenses, documents, clients, currency

app = FastAPI(title="FOPilot v2")

# Налаштування CORS (щоб фронтенд мав доступ)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.on_event("startup")
async def startup_event():
    initialize_firebase()
    Database.initialize()
    # start_scheduler() # Можна розкоментувати, якщо хочеш авто-курси валют


@app.get("/")
def read_root():
    return {"status": "ok", "version": "2.0.0"}
