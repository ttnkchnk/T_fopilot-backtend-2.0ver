from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin.auth import InvalidIdTokenError, ExpiredIdTokenError
import core.firebase as firebase

# ↓↓↓ МЫ МЕНЯЕМ ЭТУ СТРОКУ ↓↓↓
# БЫЛО: oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
# СТАЛО:
bearer_scheme = HTTPBearer()

# ↓↓↓ И МЫ МЕНЯЕМ ЭТУ ФУНКЦИЮ ↓↓↓
def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    """
    Проверяет Firebase ID Token (который приходит как Bearer token).
    """
    
    # Токен теперь находится внутри creds.credentials
    token = creds.credentials

    if firebase.auth_client is None:
        firebase.initialize_firebase()
        if firebase.auth_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Firebase not initialized"
            )
        
    try:
        decoded_token = firebase.auth_client.verify_id_token(token)
        return decoded_token
    except ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
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
