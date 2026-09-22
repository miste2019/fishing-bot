from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from bot.keyboards.reply import get_start_keyboard, get_main_menu_keyboard
from bot.keyboards.inline import (
    get_region_keyboard, CategoryCB, FavoriteCB, ReviewCB
)
from bot.config import REGIONS, REVERSE_REGIONS
from bot.database.pool import db_pool
from datetime import datetime

router = Router()


async def is_user_premium(telegram_id: int) -> bool:
    async with db_pool.acquire() as conn:
        res = await conn.fetchrow(
            "SELECT is_premium, subscription_end_date FROM users WHERE telegram_id = $1",
            telegram_id
        )
        if res and res['is_premium']:
            if res['subscription_end_date'] is None or res['subscription_end_date'] > datetime.now():
                return True
    return False


async def is_place_premium(place_id: int) -> bool:
    async with db_pool.acquire() as conn:
        res = await conn.fetchrow(
            "SELECT is_premium, premium_until FROM fishing_places WHERE id = $1",
            place_id
        )
        if res and res['is_premium']:
            if res['premium_until'] is None or res['premium_until'] > datetime.now():
                return True
    return False


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        f"👋 *Добро пожаловать, {message.from_user.first_name or 'друг'}!*\n\n"
        f"Я помогу найти лучшие места для рыбалки. Теперь с рейтингами, фото, ❤️ Избранным и 👑 Премиум-функциями!",
        parse_mode="Markdown",
        reply_markup=get_start_keyboard()
    )


@router.message(F.text == "📖 Справочник рыбака")
async def show_guide(message: Message):
    await message.answer(
        "📖 *СПРАВОЧНИК РЫБАКА*\n\n"
        "1️⃣ *Нерестовый запрет:* Соблюдается в каждом регионе.\n"
        "2️⃣ *Норма вылова:* Стандартно 5 кг на человека.\n"
        "3️⃣ *Пограничные зоны:* Требуется пропуск через Госуслуги (напр., Дагестан).\n\n"
        "📍 Выберите регион в меню!",
        parse_mode="Markdown",
        reply_markup=get_start_keyboard()
    )


@router.message(F.text == " Меню регионов")
async def show_regions_menu(message: Message):
    await message.answer(
        "📍 *Выберите регион:*",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )


@router.message(F.text == "🔙 Назад в главное меню")
async def back_to_main(message: Message):
    await message.answer(
        "🏠 *Главное меню*",
        parse_mode="Markdown",
        reply_markup=get_start_keyboard()
    )


@router.message(F.text == "👑 Премиум")
@router.message(Command("premium"))
async def cmd_premium_info(message: Message):
    user_premium = await is_user_premium(message.from_user.id)
    if user_premium:
        await message.answer(
            "👑 *Ваша премиум-подписка активна!*\n\n"
            "✅ Вам доступны точные GPS-координаты всех секретных мест, информация о глубинах и подъездах.",
            parse_mode="Markdown"
        )
    else:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="💳 Оформить за 199₽/мес", callback_data="payment_premium_user_stub")
        builder.adjust(1)
        await message.answer(
            "👑 *Премиум подписка*\n\n"
            "📍 Точные GPS-координаты ВСЕХ мест\n"
            "🗺 Информация о глубинах и рельефе\n"
            "🚗 Описание подъездов к воде\n\n"
            "💰 *Стоимость:* 199₽/месяц",
            parse_mode="Markdown",
            reply_markup=builder.as_markup()
        )


@router.message(F.text.in_(REGIONS.values()))
async def show_region(message: Message):
    region_code = REVERSE_REGIONS.get(message.text)
    if not region_code:
        return
    await message.answer(
        f"📍 *{REGIONS[region_code]}*\n\n *Выберите категорию:*",
        parse_mode="Markdown",
        reply_markup=get_region_keyboard(region_code)
    )


@router.callback_query(CategoryCB.filter())
async def handle_category(callback: CallbackQuery, callback_data: CategoryCB):
    region_name = REGIONS.get(callback_data.region, "Регион")
    category_name = CATEGORIES.get(callback_data.category, callback_data.category)
    user_premium = await is_user_premium(callback.from_user.id)

    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, title, description, price_from, link_url, phone, images, avg_rating, reviews_count, is_premium
                   FROM fishing_places 
                   WHERE region_code = $1 AND category_code = $2 AND is_active = TRUE
                   ORDER BY is_premium DESC, avg_rating DESC, sort_order ASC LIMIT 15""",
                callback_data.region, callback_data.category
            )

        if not rows:
            text = f"💎 *{category_name}*\nв {region_name}\n\n📭 Пока нет предложений."
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
        else:
            text = f"💎 *{category_name}*\nв {region_name}\n\nНайдено: {len(rows)} мест\n\n"
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()

            for i, row in enumerate(rows, 1):
                premium_badge = "👑 " if row['is_premium'] else ""
                price = f"\n💰 от {int(row['price_from']):,} ₽".replace(",", " ") if row['price_from'] else ""
                rating_str = f" ⭐ {row['avg_rating']:.1f} ({row['reviews_count']} отз.)" if row['avg_rating'] and row[
                    'avg_rating'] > 0 else ""
                desc = (row['description'][:100] + "...") if row['description'] and len(row['description']) > 100 else (
                            row['description'] or "")

                text += f"{i}. {premium_badge}*{row['title']}*{rating_str}{price}\n   {desc}\n"
                builder.button(text=f"🔗 Подробнее #{row['id']}", callback_data=f"place_detail_{row['id']}")

                if not user_premium and row['is_premium']:
                    builder.button(text=f"📡 Координаты (99₽)", callback_data=f"buy_coords_{row['id']}")
                else:
                    builder.button(text=f"❤️ В избранное",
                                   callback_data=FavoriteCB(action="add", place_id=row['id']).pack())
                text += "\n"

        builder.button(text="🔙 Назад к регионам", callback_data="back_to_regions")
        builder.adjust(2)
        await callback.message.edit_text(text, parse_mode="Markdown", disable_web_page_preview=True,
                                         reply_markup=builder.as_markup())
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка загрузки категорий: {e}")
        await callback.answer("Ошибка загрузки данных", show_alert=True)
    await callback.answer()


@router.callback_query(F.data.startswith("buy_coords_"))
async def buy_gps_coords(callback: CallbackQuery):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Купить координаты (99₽)", callback_data="payment_coords_stub")
    builder.button(text="👑 Оформить Премиум (199₽/мес)", callback_data="payment_premium_user_stub")
    builder.button(text=" Отмена", callback_data="back_to_regions")
    builder.adjust(1)
    await callback.message.answer(
        "📍 *Точные GPS-координаты*\n\n"
        "Это секретное место! Чтобы получить точные координаты для навигатора, информацию о глубинах и описание подъезда, оформите разовый доступ или премиум-подписку.",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("place_detail_"))
async def handle_place_detail(callback: CallbackQuery):
    place_id = int(callback.data.split("_")[2])
    user_premium = await is_user_premium(callback.from_user.id)
    place_premium = await is_place_premium(place_id)

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT title, description, price_from, link_url, phone, images, avg_rating, reviews_count, exact_latitude, exact_longitude, depth_info, approach_description FROM fishing_places WHERE id = $1",
                place_id
            )
        if not row:
            return await callback.answer("Место не найдено", show_alert=True)

        text = f"📍 *{row['title']}*\n"
        if row['avg_rating'] and row['avg_rating'] > 0:
            text += f"⭐ Рейтинг: {row['avg_rating']:.1f} ({row['reviews_count']} отзывов)\n"
        if row['price_from']:
            text += f"💰 Цена: от {int(row['price_from']):,} ₽\n"
        text += f"\n {row['description']}\n"

        if (user_premium or place_premium) and row['exact_latitude']:
            text += f"\n *Точные координаты:*\nШирота: `{row['exact_latitude']}`\nДолгота: `{row['exact_longitude']}`\n"
            text += f"🗺 [Открыть в Яндекс.Картах](https://yandex.ru/maps/?pt={row['exact_longitude']},{row['exact_latitude']}&z=15&l=map)\n"
            if row['depth_info']:
                text += f"📊 *Глубины:* {row['depth_info']}\n"
            if row['approach_description']:
                text += f"🚗 *Подъезд:* {row['approach_description']}\n"
        elif row['exact_latitude'] and not user_premium:
            text += f"\n🔒 *Точные координаты скрыты.* Нажмите ' Координаты' в списке, чтобы открыть их."

        if row['phone']:
            text += f"\n📞 Телефон: `{row['phone']}`\n"
        if row['images']:
            text += f"\n📸 [Смотреть фото]({row['images'][0]})\n"
        if row['link_url']:
            text += f"🔗 [Сайт / Бронь]({row['link_url']})\n"

        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="❤️ Добавить в избранное", callback_data=FavoriteCB(action="add", place_id=place_id).pack())
        builder.button(text="⭐ Оставить отзыв",
                       callback_data=ReviewCB(region="any", category="any", place_id=place_id).pack())
        builder.button(text="🔙 Назад", callback_data="back_to_regions")
        builder.adjust(1)
        await callback.message.edit_text(text, parse_mode="Markdown", disable_web_page_preview=False,
                                         reply_markup=builder.as_markup())
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка detail: {e}")
    await callback.answer()


@router.callback_query(F.data == "back_to_regions")
async def back_to_regions(callback: CallbackQuery):
    await callback.message.edit_text(
        "📍 *Выберите регион:*",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(FavoriteCB.filter())
async def handle_favorite(callback: CallbackQuery, callback_data: FavoriteCB):
    user_id = callback.from_user.id
    place_id = callback_data.place_id
    try:
        async with db_pool.acquire() as conn:
            if callback_data.action == "add":
                await conn.execute(
                    "INSERT INTO favorites (telegram_id, place_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    user_id, place_id
                )
                await callback.answer("❤️ Добавлено в избранное!", show_alert=True)
            elif callback_data.action == "remove":
                await conn.execute(
                    "DELETE FROM favorites WHERE telegram_id = $1 AND place_id = $2",
                    user_id, place_id
                )
                await callback.answer("💔 Удалено из избранного", show_alert=True)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка избранного: {e}")
    await callback.answer()


@router.message(F.text == "❤️ Избранное")
async def show_favorites(message: Message):
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT fp.id, fp.title, fp.avg_rating, fp.price_from, r.name as region
                   FROM favorites f 
                   JOIN fishing_places fp ON f.place_id = fp.id 
                   JOIN regions r ON fp.region_code = r.code
                   WHERE f.telegram_id = $1 AND fp.is_active = TRUE 
                   ORDER BY f.created_at DESC""",
                message.from_user.id
            )
        if not rows:
            await message.answer(
                "💔 *Ваш список избранного пуст.*\n\nНажмите ❤️ на карточке места, чтобы сохранить его здесь.",
                parse_mode="Markdown",
                reply_markup=get_start_keyboard()
            )
        else:
            text = "❤️ *Ваши избранные места:*\n\n"
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            for row in rows:
                rating = f" ⭐ {row['avg_rating']:.1f}" if row['avg_rating'] and row['avg_rating'] > 0 else ""
                text += f"📍 *{row['title']}*{rating}\n   {row['region']}\n\n"
                builder.button(text=f"🗑 Убрать #{row['id']}",
                               callback_data=FavoriteCB(action="remove", place_id=row['id']).pack())
            builder.adjust(1)
            await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка показа избранного: {e}")