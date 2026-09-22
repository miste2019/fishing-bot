import requests
from bot.config import settings
import logging

logger = logging.getLogger(__name__)

class YandexGPT:
    def __init__(self, iam_token: str, folder_id: str):
        self.iam_token = iam_token
        self.folder_id = folder_id
        self.url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

    def generate_description(self, title: str, region: str, category: str, price: float = 0) -> str:
        system_prompt = """Ты — опытный копирайтер, специализирующийся на туризме и рыбалке.
Твоя задача — создавать короткие, продающие описания рыболовных мест.
Правила:
- Максимум 150-200 символов
- Используй эмодзи в начале (📍 для локации, 🎣 для рыбы, ✨ для фишки)
- Пиши конкретно: названия рек, виды рыбы, расстояния
- Добавь "фишку" места — что делает его уникальным
- Не используй общие фразы типа "отличное место"
- Если цена > 5000, упомяни премиум-сервис
- Если цена = 0, это дикое место — подчеркни природу"""

        price_text = f"Цена: от {int(price)}₽/сутки" if price > 0 else "Бесплатно (дикое место)"
        user_prompt = f"""Создай описание для рыболовного места:
Название: {title}
Регион: {region}
Категория: {category}
{price_text}

Формат ответа (строго):
📍 Локация: [конкретное место]
🎣 Рыба: [виды рыбы]
✨ Фишка: [уникальная особенность]"""

        headers = {"Authorization": f"Bearer {self.iam_token}", "Content-Type": "application/json"}
        payload = {
            "modelUri": f"gpt://{self.folder_id}/yandexgpt/latest",
            "completionOptions": {"stream": False, "temperature": 0.7, "maxTokens": "500"},
            "messages": [{"role": "system", "text": system_prompt}, {"role": "user", "text": user_prompt}]
        }

        try:
            response = requests.post(self.url, headers=headers, json=payload, timeout=30)
            result = response.json()
            if 'result' in result and 'alternatives' in result['result']:
                return result['result']['alternatives'][0]['message']['text']
            else:
                return f"❌ Ошибка API: {result.get('message', 'Неизвестная ошибка')}"
        except Exception as e:
            return f"❌ Ошибка соединения: {str(e)}"

ai_generator = None

async def init_ai():
    global ai_generator
    try:
        ai_generator = YandexGPT(
            iam_token=settings.yandex_iam_token,
            folder_id=settings.yandex_folder_id
        )
        logger.info("✅ YandexGPT инициализирован")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации ИИ: {e}")