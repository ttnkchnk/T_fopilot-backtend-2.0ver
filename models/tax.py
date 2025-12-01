# Pydantic моделі для податків та платежів

from pydantic import BaseModel

class TaxCalculationRequest(BaseModel):
    quarterly_income: float

class TaxCalculationResponse(BaseModel):
    single_tax: float
    social_contribution: float
    total_tax: float

class PaymentRequest(BaseModel):
    amount: float  # Сума в гривнях (напр. 5280.00)
    destination: str # Призначення платежу (напр. "Сплата ЄСВ за 4 квартал")

class PaymentResponse(BaseModel):
    invoice_id: str
    payment_page_url: str