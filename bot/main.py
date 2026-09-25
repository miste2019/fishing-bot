import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import ErrorEvent
from bot.config import settings
from bot.database.pool import init_db, close_db
from bot.handlers import user, admin
from bot.middlewares.user_tracking import UserTrackingMiddleware
from bot.services.yandex_gpt import init_ai

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=settings.bot_token)
dp = Dispatcher()

# Регистрируем роутеры
dp.include_router(user.router)
dp.include_router(admin.router)

# Добавляем middleware
dp.message.middleware(UserTrackingMiddleware())
dp.callback_query.middleware(UserTrackingMiddleware())

@dp.errors()
async def errors_handler(event: ErrorEvent):
    logger.error(f"Глобальная ошибка: {event.exception}", exc_info=True)
    return True

@dp.shutdown()
async def on_shutdown():
    await close_db()

async def main():
    await init_db()
    await init_ai()
    logger.info(" Рыболовный бот v2.0 (с ИИ и Премиум) запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
