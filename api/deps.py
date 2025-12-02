from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from firebase_admin.auth import InvalidIdTokenError, ExpiredIdTokenError
import core.firebase as firebase
from fastapi import HTTPException

bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> dict:
    """
    Проверяет Firebase ID Token (который приходит как Bearer token).
    Якщо токена немає — повертає локального користувача для dev.
    Якщо токен є, але прострочений/невірний — повертає 401, щоб фронт оновив сесію.
    """
    if not creds or not creds.credentials:
        return {"uid": "local-dev"}

    token = creds.credentials

    if firebase.auth_client is None:
        firebase.initialize_firebase()
        if firebase.auth_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Firebase not initialized"
            )
        
    try:
        # Додаємо невеликий допуск по часу (макс 60 сек за Firebase SDK)
        decoded_token = firebase.auth_client.verify_id_token(token, clock_skew_seconds=60)
        return decoded_token
    except (ExpiredIdTokenError, InvalidIdTokenError) as e:
        print(f"Token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        print(f"Token validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Проста перевірка адмінського доступу. Для dev дозволяємо uid=local-dev.
    """
    if current_user.get("uid") == "local-dev":
        return current_user
    if current_user.get("admin") or current_user.get("is_admin"):
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required",
    )



# # Залежності (Dependencies) для FastAPI

# from fastapi import Depends, HTTPException, status
# from fastapi.security import OAuth2PasswordBearer
# from firebase_admin.auth import InvalidIdTokenError, ExpiredIdTokenError
# from core.firebase import auth_client

# # Ця схема лише "вчить" Swagger показувати кнопку "Authorize"
# # Реальна логіка бере токен з заголовка Authorization
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
#     """
#     Перевіряє Firebase ID Token, який надійшов у заголовку Authorization.
#     Повертає розкодований токен (словник з даними користувача, вкл. 'uid').
#     """
#     try:
#         # Верифікуємо токен, який надіслав фронтенд
#         decoded_token = auth_client.verify_id_token(token)
#         return decoded_token
#     except ExpiredIdTokenError:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Token has expired",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#     except InvalidIdTokenError:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid token",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#     except Exception:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Could not validate credentials",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
