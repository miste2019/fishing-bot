import asyncpg
from bot.config import settings
import logging

logger = logging.getLogger(__name__)
db_pool = None

async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=10
    )
    logger.info("✅ Подключение к PostgreSQL установлено")

async def close_db():
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info(" Соединение с БД закрыто")