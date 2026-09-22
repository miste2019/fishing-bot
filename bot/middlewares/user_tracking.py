from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from bot.database.pool import db_pool

class UserTrackingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: TelegramObject, data: dict):
        if user := getattr(event, "from_user", None):
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO users (telegram_id, username, first_name) 
                       VALUES ($1, $2, $3) ON CONFLICT (telegram_id) DO UPDATE 
                       SET username = COALESCE($2, users.username), 
                           first_name = COALESCE($3, users.first_name),
                           last_active = CURRENT_TIMESTAMP""",
                    user.id, user.username, user.first_name
                )
        return await handler(event, data)