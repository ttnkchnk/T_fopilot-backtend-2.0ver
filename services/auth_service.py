# Сервісний шар для логіки автентифікації
from fastapi import HTTPException
import core.firebase as firebase
from models.user import UserInDB, UserUpdate


def create_user_profile(uid: str, email: str, first_name: str, last_name: str, middle_name: str | None = None, phone: str | None = None) -> UserInDB:
    """
    Створює документ користувача в колекції 'users' у Firestore.
    """
    if firebase.db is None:
        firebase.initialize_firebase()
    user_doc_data = {
        "uid": uid,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "middle_name": middle_name,
        "fop_group": 3,
        "tax_rate": 0.05,
        "onboarding_completed": False,
        "onboarding_data": None,
        "phone": phone,
    }

    # Використовуємо UID з Auth як ID документу в Firestore
    firebase.db.collection("users").document(uid).set(user_doc_data)

    return UserInDB(**user_doc_data)


def get_user_profile(uid: str) -> UserInDB | None:
    """
    Отримує профіль користувача з Firestore за його UID.
    """
    if firebase.db is None:
        firebase.initialize_firebase()
    doc_ref = firebase.db.collection("users").document(uid)
    doc = doc_ref.get()

    if doc.exists:
        return UserInDB(**doc.to_dict())
    return None

def update_user_profile(uid: str, data: UserUpdate) -> UserInDB:
    """
    Обновляет профиль пользователя в ДВУХ местах:
    1. Firebase Authentication (для display_name)
    2. Firestore (для first_name, last_name)
    """
    # 0. Гарантируем инициализацию Firebase (Auth + Firestore)
    if firebase.db is None or firebase.auth_client is None:
        firebase.initialize_firebase()
    
    # 1. Обновляем Firebase Authentication (чтобы 'display_name' совпадало)
    try:
        display_parts = [data.first_name, data.middle_name or "", data.last_name]
        firebase.auth_client.update_user(
            uid,
            display_name=" ".join(part for part in display_parts if part).strip()
        )
    except Exception as e:
        print(f"Ошибка обновления Firebase Auth: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обновления профиля в Auth")

    # 2. Обновляем Firestore (где хранятся наши 'first_name', 'last_name')
    try:
        doc_ref = firebase.db.collection("users").document(uid)
        update_payload = {
            "first_name": data.first_name,
            "last_name": data.last_name,
            "middle_name": data.middle_name,
        }
        # опционально обновляем телефон
        if hasattr(data, "phone"):
            update_payload["phone"] = data.phone
        doc_ref.update(update_payload)
    except Exception as e:
        print(f"Ошибка обновления Firestore: {e}")
        raise HTTPException(status_code=500, detail="Ошибка обновления профиля в Firestore")
        
    # 3. Возвращаем обновленный профиль (вызываем нашу 'get_user_profile')
    return get_user_profile(uid)
