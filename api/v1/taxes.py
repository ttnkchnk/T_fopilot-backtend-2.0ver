# API роутер для податків

from fastapi import APIRouter, Depends
from models.tax import TaxCalculationRequest, TaxCalculationResponse, PaymentRequest, PaymentResponse
from services import tax_service
from api.deps import get_current_user

router = APIRouter()

@router.post("/calculate", response_model=TaxCalculationResponse)
def calculate_taxes_endpoint(
    request: TaxCalculationRequest,
    current_user: dict = Depends(get_current_user)
):
    
    user_uid = current_user.get("uid")
    # ↓↓↓ ОСЬ ТУТ БУЛА ПОМИЛКА ↓↓↓
    # Ти не передавав user_uid, який вимагає tax_service
    return tax_service.calculate_taxes(request, user_uid)

@router.post("/create-payment", response_model=PaymentResponse)
async def create_payment_endpoint(
    request: PaymentRequest,
    current_user: dict = Depends(get_current_user)
):
    return await tax_service.create_mono_payment(request)

# from fastapi import APIRouter, Depends
# from models.tax import TaxCalculationRequest, TaxCalculationResponse, PaymentRequest, PaymentResponse
# from services import tax_service
# from api.deps import get_current_user

# router = APIRouter()

# @router.post("/calculate", response_model=TaxCalculationResponse)
# def calculate_taxes_endpoint(
#     request: TaxCalculationRequest,
#     current_user: dict = Depends(get_current_user)
# ):
#     """
#     Розраховує податки (ЄП та ЄСВ) на основі квартального доходу.
#     Доступно лише для автентифікованих користувачів.
#     """
#     return tax_service.calculate_taxes(request)

# @router.post("/create-payment", response_model=PaymentResponse)
# async def create_payment_endpoint(
#     request: PaymentRequest,
#     current_user: dict = Depends(get_current_user)
# ):
#     """
#     Створює платіжне посилання Monobank для сплати податку.
#     Доступно лише для автентифікованих користувачів.
#     """
#     return await tax_service.create_mono_payment(request)