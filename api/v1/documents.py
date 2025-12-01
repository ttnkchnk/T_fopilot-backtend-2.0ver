from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.deps import get_current_user
from services.ai import check_declaration_with_ai

router = APIRouter()


class DeclarationField(BaseModel):
    code: str
    label: str
    value: str


class DeclarationAICheckResponse(BaseModel):
    is_valid: bool
    issues: List[str]
    suggestions: List[str]


@router.post("/declaration/ai-check", response_model=DeclarationAICheckResponse)
async def declaration_ai_check(
    declaration: List[DeclarationField],
    current_user: dict = Depends(get_current_user),
):
    """
    Перевіряє заповнену декларацію ФОП за допомогою Gemini.
    """
    try:
        user_label = current_user.get("name") or current_user.get("email") or current_user.get("uid")
    except Exception:
        user_label = None

    try:
        result = await check_declaration_with_ai(declaration, user_label=user_label)
        return DeclarationAICheckResponse(**result)
    except Exception as e:
        print(f"Declaration AI check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Помилка перевірки декларації AI",
        )
