# Сервісний шар для логіки податків

import httpx
from fastapi import HTTPException, status
from core.config import settings  # Импортируем наши настройки
from models.tax import TaxCalculationRequest, TaxCalculationResponse, PaymentRequest, PaymentResponse
# Импортируем сервис для получения профиля
from services import auth_service 

# Мы больше не храним константы здесь.
# Мы будем брать их из settings (для ЕСВ) и из профиля (для ставки).

def calculate_taxes(data: TaxCalculationRequest, user_uid: str) -> TaxCalculationResponse:
    """
    Рассчитывает налоги для ФОП.
    Теперь он использует ставку из профиля пользователя
    и ЕСВ из файла .env.
    """
    
    # 1. Получаем профиль пользователя из Firestore
    user_profile = auth_service.get_user_profile(user_uid)
    if user_profile is None:
        # Этого не должно случиться, если пользователь авторизован,
        # но это безопасная проверка
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found in Firestore"
        )

    # 2. Берем ставку налога ИЗ ПРОФИЛЯ ПОЛЬЗОВАТЕЛЯ
    single_tax_rate = user_profile.tax_rate  # (например, 0.05 или 0.02)
    
    # 3. Берем ЕСВ ИЗ .env (через settings)
    social_contribution_monthly = settings.MIN_SOCIAL_CONTRIBUTION_MONTHLY
    social_contribution_quarterly = social_contribution_monthly * 3

    # 4. Расчет
    single_tax = round(data.quarterly_income * single_tax_rate, 2)
    social_contribution = round(social_contribution_quarterly, 2)
    
    total_tax = round(single_tax + social_contribution, 2)
    
    return TaxCalculationResponse(
        single_tax=single_tax,
        social_contribution=social_contribution,
        total_tax=total_tax
    )

async def create_mono_payment(payment_data: PaymentRequest) -> PaymentResponse:
    """
    Создает инвойс (счет) на оплату через Monobank Acquiring API.
    (Этот код не изменился)
    """
    headers = {
        "X-Token": settings.MONOBANK_API_TOKEN
    }
    
    payload = {
        "amount": int(payment_data.amount * 100),  # Monobank принимает сумму в копейках
        "ccy": 980,  # 980 = UAH
        "merchantPaymInfo": {
            "destination": payment_data.destination
        },
        "redirectUrl": "https://github.com/andrewgindich/FOPilot" # Сторінка успішної оплати
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.MONOBANK_API_URL}/api/merchant/invoice/create",
                json=payload,
                headers=headers
            )
            
            response.raise_for_status()  # Генерує помилку, якщо статус не 2xx
            
            data = response.json()
            return PaymentResponse(
                invoice_id=data["invoiceId"],
                payment_page_url=data["pageUrl"]
            )
            
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"Monobank API error: {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal error: {str(e)}"
            )


# import httpx
# from fastapi import HTTPException, status
# from core.config import settings
# from models.tax import TaxCalculationRequest, TaxCalculationResponse, PaymentRequest, PaymentResponse

# # Константи для розрахунку (на базі даних 2025 року)
# # Мінімальна ЗП = 8000 грн
# # ЄСВ (22% від МЗП) = 1760 грн/місяць
# MIN_SOCIAL_CONTRIBUTION_MONTHLY = 1760.00
# MIN_SOCIAL_CONTRIBUTION_QUARTERLY = MIN_SOCIAL_CONTRIBUTION_MONTHLY * 3
# SINGLE_TAX_RATE = 0.05  # 5% для 3-ї групи


# def calculate_taxes(data: TaxCalculationRequest) -> TaxCalculationResponse:
#     """
#     Розраховує податки для ФОП 3-ї групи.
#     """
#     single_tax = round(data.quarterly_income * SINGLE_TAX_RATE, 2)
#     social_contribution = MIN_SOCIAL_CONTRIBUTION_QUARTERLY

#     total_tax = round(single_tax + social_contribution, 2)

#     return TaxCalculationResponse(
#         single_tax=single_tax,
#         social_contribution=social_contribution,
#         total_tax=total_tax
#     )


# async def create_mono_payment(payment_data: PaymentRequest) -> PaymentResponse:
#     """
#     Створює інвойс (рахунок) на оплату через Monobank Acquiring API.
#     """
#     headers = {
#         "X-Token": settings.MONOBANK_API_TOKEN
#     }

#     payload = {
#         "amount": int(payment_data.amount * 100),  # Monobank приймає суму в копійках
#         "ccy": 980,  # 980 = UAH
#         "merchantPaymInfo": {
#             "destination": payment_data.destination
#         },
#         "redirectUrl": "https://github.com/andrewgindich/FOPilot"
#     }

#     async with httpx.AsyncClient() as client:
#         try:
#             response = await client.post(
#                 f"{settings.MONOBANK_API_URL}/api/merchant/invoice/create",
#                 json=payload,
#                 headers=headers
#             )

#             response.raise_for_status()  # Генерує помилку, якщо статус не 2xx

#             data = response.json()
#             return PaymentResponse(
#                 invoice_id=data["invoiceId"],
#                 payment_page_url=data["pageUrl"]
#             )

#         except httpx.HTTPStatusError as e:
#             raise HTTPException(
#                 status_code=e.response.status_code,
#                 detail=f"Monobank API error: {e.response.text}"
#             )
#         except Exception as e:
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail=f"Internal error: {str(e)}"
#             )