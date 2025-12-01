import google.generativeai as genai
from config import settings
from database import Database


class AIService:
    def __init__(self):
        # Налаштування Gemini API
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        self.db = Database.get_db()

    async def get_financial_context(self, user_uid: str) -> str:
        """
        Метод RAG: Збирає останні транзакції користувача, 
        щоб ШІ знав контекст.
        """
        # Отримуємо останні 10 транзакцій
        docs = self.db.collection("transactions")\
            .where("user_uid", "==", user_uid)\
            .order_by("date", direction="DESCENDING")\
            .limit(10)\
            .stream()

        transactions_text = "Останні фінансові операції:\n"
        total_income = 0.0

        for doc in docs:
            data = doc.to_dict()
            t_type = "Дохід" if data['type'] == 'income' else "Витрата"
            amount = data.get('amount_uah', 0)
            if data['type'] == 'income':
                total_income += amount

            transactions_text += f"- {data['date'].strftime('%Y-%m-%d')}: {t_type} {amount:.2f} UAH ({data.get('category')})\n"

        summary = f"\nЗагальний дохід (з останніх завантажених): {total_income:.2f} UAH"
        return transactions_text + summary

    async def generate_chat_response(self, user_message: str, user_uid: str) -> str:
        """
        Генерація відповіді з урахуванням контексту (RAG)
        """
        # 1. Отримуємо фінансові дані (Retrieval)
        context_data = await self.get_financial_context(user_uid)

        # 2. Формуємо системний промпт (Augmentation)
        system_prompt = f"""
        Ти - FOPilot, розумний фінансовий асистент для ФОП 3-ї групи в Україні.
        Твоя мета - допомагати підприємцю з податками та обліком.
        
        Ось фінансові дані користувача:
        {context_data}
        
        Питання користувача: {user_message}
        
        Відповідай коротко, професійно, українською мовою. Використовуй надані цифри для відповіді.
        """

        # 3. Генеруємо відповідь (Generation)
        try:
            response = self.model.generate_content(system_prompt)
            return response.text
        except Exception as e:
            print(f"AI Error: {e}")
            return "Вибач, я зараз не можу зв'язатися з сервером AI. Спробуй пізніше."

    async def validate_declaration(self, declaration_data: dict) -> dict:
        """
        Агент-аудитор: перевіряє декларацію на помилки
        """
        prompt = f"""
        Ти - податковий аудитор. Перевір дані декларації ФОП 3 групи:
        {declaration_data}
        
        Правила:
        1. Ставка податку має бути 5% від доходу.
        2. Якщо дохід > 0, податок не може бути 0.
        
        Поверни JSON у форматі:
        {{
            "is_valid": true/false,
            "issues": ["список помилок українською"],
            "suggestions": ["поради"]
        }}
        """
        response = self.model.generate_content(prompt)
        return {"raw_ai_response": response.text}
