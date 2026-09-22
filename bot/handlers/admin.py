from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.keyboards.reply import get_start_keyboard
from bot.keyboards.inline import (
    get_admin_main_keyboard, AdminPlaceCB, AdminFieldCB
)
from bot.config import REGIONS, CATEGORIES, settings
from bot.database.pool import db_pool
from bot.services.yandex_gpt import ai_generator
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
router = Router()


class AddPlace(StatesGroup):
    region = State()
    category = State()
    title = State()
    description = State()
    price = State()
    link = State()
    phone = State()
    images = State()


class EditPlace(StatesGroup):
    place_id = State()
    field = State()
    value = State()


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer(
            f"⛔ *Нет доступа!* Ваш ID: `{message.from_user.id}`",
            parse_mode="Markdown"
        )
    await message.answer(
        "⚙️ *Админ-панель*",
        parse_mode="Markdown",
        reply_markup=get_admin_main_keyboard()
    )


@router.callback_query(F.data == "admin_add")
async def admin_start_add(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for code, name in REGIONS.items():
        builder.button(text=name, callback_data=f"areg_{code}")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(2)
    await callback.message.edit_text(
        "📍 *Шаг 1/8: Выберите регион*",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    await state.set_state(AddPlace.region)
    await callback.answer()


@router.callback_query(F.data.startswith("areg_"), AddPlace.region)
async def admin_set_region(callback: CallbackQuery, state: FSMContext):
    region = callback.data.replace("areg_", "")
    await state.update_data(region=region)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for code, name in CATEGORIES.items():
        builder.button(text=name, callback_data=f"acat_{code}")
    builder.button(text="❌ Отмена", callback_data="admin_cancel")
    builder.adjust(1)
    await callback.message.edit_text(
        f"✅ Регион: *{REGIONS[region]}*\n\n *Шаг 2/8: Категория*",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    await state.set_state(AddPlace.category)
    await callback.answer()


@router.callback_query(F.data.startswith("acat_"), AddPlace.category)
async def admin_set_category(callback: CallbackQuery, state: FSMContext):
    cat = callback.data.replace("acat_", "")
    await state.update_data(category=cat)
    await callback.message.edit_text(
        f"✅ Категория: *{CATEGORIES[cat]}*\n\n✏️ *Шаг 3/8: Введите название*",
        parse_mode="Markdown"
    )
    await state.set_state(AddPlace.title)
    await callback.answer()


@router.message(AddPlace.title)
async def admin_set_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("📝 *Шаг 4/8: Введите описание*")
    await state.set_state(AddPlace.description)


@router.message(AddPlace.description)
async def admin_set_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("💰 *Шаг 5/8: Введите цену (число или 0)*")
    await state.set_state(AddPlace.price)


@router.message(AddPlace.price)
async def admin_set_price(message: Message, state: FSMContext):
    try:
        await state.update_data(price=float(message.text.replace(",", ".")))
        await message.answer("🔗 *Шаг 6/8: Ссылка на сайт (или `-`)*")
        await state.set_state(AddPlace.link)
    except ValueError:
        await message.answer("⚠️ Введите корректное число!")


@router.message(AddPlace.link)
async def admin_set_link(message: Message, state: FSMContext):
    link = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(link=link)
    await message.answer("📞 *Шаг 7/8: Телефон для связи (или `-`)*")
    await state.set_state(AddPlace.phone)


@router.message(AddPlace.phone)
async def admin_set_phone(message: Message, state: FSMContext):
    phone = None if message.text.strip() == "-" else message.text.strip()
    await state.update_data(phone=phone)
    await message.answer(
        "📸 *Шаг 8/8: Ссылки на фото через запятую (или `-`)*\nПример: `http://img1.jpg, http://img2.jpg`"
    )
    await state.set_state(AddPlace.images)


@router.message(AddPlace.images)
async def admin_save(message: Message, state: FSMContext):
    images_text = message.text.strip()
    images_list = [img.strip() for img in images_text.split(',')] if images_text != "-" else None
    data = await state.get_data()
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO fishing_places (region_code, category_code, title, description, price_from, link_url, phone, images, is_active, sort_order)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, TRUE, 0)""",
                data['region'], data['category'], data['title'], data['description'],
                data['price'], data['link'], data['phone'], images_list
            )
        await message.answer(
            f"✅ *Добавлено!*\n\n📍 {REGIONS[data['region']]}\n✏️ {data['title']}",
            parse_mode="Markdown",
            reply_markup=get_admin_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка БД: {e}")
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        await state.clear()


@router.callback_query(F.data == "admin_manage")
async def admin_manage(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа", show_alert=True)
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, title, price_from, region_code, category_code, avg_rating, reviews_count, phone, is_active, is_premium FROM fishing_places ORDER BY id DESC LIMIT 15"
            )
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        if not rows:
            text = "📭 База данных пуста"
            builder.button(text="➕ Добавить первое место", callback_data="admin_add")
        else:
            text = "📋 *Управление местами (последние 15):*\n\n"
            for row in rows:
                rating_str = f" ⭐ {row['avg_rating']:.1f} ({row['reviews_count']})" if row['avg_rating'] and row[
                    'avg_rating'] > 0 else ""
                status_emoji = "✅" if row['is_active'] else "❌"
                premium_emoji = "" if row['is_premium'] else ""
                price_str = f" | {int(row['price_from']):,}₽".replace(",", " ") if row['price_from'] else ""
                region_name = REGIONS.get(row['region_code'], row['region_code'])
                text += f"{status_emoji}{premium_emoji} ID {row['id']}: *{row['title']}*{rating_str}\n    {region_name}{price_str}\n\n"
                builder.button(text=f"✏️ #{row['id']}",
                               callback_data=AdminPlaceCB(action="edit", place_id=row['id']).pack())
                builder.button(text=f"🗑 #{row['id']}",
                               callback_data=AdminPlaceCB(action="delete", place_id=row['id']).pack())
        builder.button(text="➕ Добавить", callback_data="admin_add")
        builder.button(text="🔙 Назад в админку", callback_data="admin_main")
        builder.adjust(2)
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    except Exception as e:
        logger.error(f"Ошибка управления: {e}")
        await callback.answer("❌ Ошибка загрузки", show_alert=True)
    await callback.answer()


@router.callback_query(AdminPlaceCB.filter(F.action == "edit"))
async def admin_edit_select(callback: CallbackQuery, callback_data: AdminPlaceCB, state: FSMContext):
    await state.update_data(place_id=callback_data.place_id)
    try:
        async with db_pool.acquire() as conn:
            place = await conn.fetchrow(
                "SELECT title, description, price_from, link_url, phone, images, region_code, category_code, is_active, is_premium FROM fishing_places WHERE id = $1",
                callback_data.place_id
            )
        if not place:
            return await callback.answer("❌ Место не найдено", show_alert=True)
        region_name = REGIONS.get(place['region_code'], place['region_code'])
        category_name = CATEGORIES.get(place['category_code'], place['category_code'])
        status_text = "✅ Активно" if place['is_active'] else "❌ Скрыто"
        premium_text = "👑 Премиум" if place['is_premium'] else "Обычное"

        text = f"✏️ *Редактирование места #{callback_data.place_id}*\n\n"
        text += f"📍 {region_name} | {category_name}\n *{place['title']}*\n💰 {place['price_from'] or 0} ₽\n"
        if place['phone']:
            text += f"📞 {place['phone']}\n"
        text += f"\n{status_text} | {premium_text}\n\n"
        text += f"📄 Описание: {place['description'][:100]}..." if place['description'] and len(
            place['description']) > 100 else f"📄 {place['description'] or 'Нет'}"

        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="✏️ Название",
                       callback_data=AdminFieldCB(field="title", place_id=callback_data.place_id).pack())
        builder.button(text=" Описание",
                       callback_data=AdminFieldCB(field="description", place_id=callback_data.place_id).pack())
        builder.button(text="💰 Цена", callback_data=AdminFieldCB(field="price", place_id=callback_data.place_id).pack())
        builder.button(text=" Ссылка", callback_data=AdminFieldCB(field="link", place_id=callback_data.place_id).pack())
        builder.button(text="📞 Телефон",
                       callback_data=AdminFieldCB(field="phone", place_id=callback_data.place_id).pack())
        builder.button(text="📸 Фото",
                       callback_data=AdminFieldCB(field="images", place_id=callback_data.place_id).pack())
        builder.button(text=" Статус (Вкл/Выкл)",
                       callback_data=AdminPlaceCB(action="toggle_status", place_id=callback_data.place_id).pack())
        builder.button(text="👑 Премиум настройка",
                       callback_data=AdminPlaceCB(action="make_premium", place_id=callback_data.place_id).pack())
        builder.button(text="🤖 Сгенерировать описание",
                       callback_data=AdminPlaceCB(action="ai_generate", place_id=callback_data.place_id).pack())
        builder.button(text="🔙 Назад к списку", callback_data="admin_manage")
        builder.adjust(2)
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    except Exception as e:
        logger.error(f"Ошибка редактирования: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)
    await callback.answer()


@router.callback_query(AdminPlaceCB.filter(F.action == "ai_generate"))
async def admin_ai_generate(callback: CallbackQuery, callback_data: AdminPlaceCB, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа", show_alert=True)
    if not ai_generator:
        return await callback.answer("❌ ИИ не инициализирован. Проверьте .env", show_alert=True)

    await callback.answer("⏳ Генерирую описание...", show_alert=False)
    try:
        async with db_pool.acquire() as conn:
            place = await conn.fetchrow(
                "SELECT title, region_code, category_code, price_from FROM fishing_places WHERE id = $1",
                callback_data.place_id
            )
        if not place:
            return await callback.answer("❌ Место не найдено", show_alert=True)

        description = ai_generator.generate_description(
            title=place['title'],
            region=REGIONS.get(place['region_code'], place['region_code']),
            category=CATEGORIES.get(place['category_code'], place['category_code']),
            price=place['price_from'] or 0
        )

        await state.update_data(generated_description=description, place_id=callback_data.place_id)

        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Сохранить в базу",
                       callback_data=AdminPlaceCB(action="save_ai_desc", place_id=callback_data.place_id).pack())
        builder.button(text="🔄 Перегенерировать",
                       callback_data=AdminPlaceCB(action="ai_generate", place_id=callback_data.place_id).pack())
        builder.button(text="❌ Отмена",
                       callback_data=AdminPlaceCB(action="edit", place_id=callback_data.place_id).pack())
        builder.adjust(1)

        await callback.message.answer(
            f"🤖 *Сгенерированное описание:*\n\n{description}\n\n_Нажмите 'Сохранить', чтобы обновить место, или 'Перегенерировать' для нового варианта._",
            parse_mode="Markdown",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logger.error(f"Ошибка генерации: {e}")
        await callback.answer(f" Ошибка: {str(e)}", show_alert=True)


@router.callback_query(AdminPlaceCB.filter(F.action == "save_ai_desc"))
async def admin_save_ai_description(callback: CallbackQuery, callback_data: AdminPlaceCB, state: FSMContext):
    try:
        data = await state.get_data()
        description = data.get('generated_description')
        place_id = data.get('place_id')
        if not description or not place_id:
            return await callback.answer("❌ Данные не найдены, попробуйте снова", show_alert=True)

        async with db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE fishing_places SET description = $1 WHERE id = $2",
                description, place_id
            )

        await callback.message.answer(
            "✅ Описание успешно сохранено в базу!",
            reply_markup=get_admin_main_keyboard()
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")
        await callback.answer("❌ Ошибка сохранения", show_alert=True)


@router.callback_query(AdminPlaceCB.filter(F.action == "make_premium"))
async def admin_make_premium(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return await callback.answer("⛔", show_alert=True)
    await state.update_data(place_id=callback_data.place_id)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ На 7 дней (499₽)", callback_data="premium_duration_7")
    builder.button(text="✅ На 30 дней (1499₽)", callback_data="premium_duration_30")
    builder.button(text="✅ Снять премиум", callback_data="premium_duration_remove")
    builder.button(text="❌ Отмена", callback_data=AdminPlaceCB(action="edit", place_id=callback_data.place_id).pack())
    builder.adjust(1)
    await callback.message.answer(
        f"👑 *Премиум размещение для места #{callback_data.place_id}*\n\nВыберите срок:",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("premium_duration_"))
async def admin_set_premium_duration(callback: CallbackQuery, state: FSMContext):
    duration = callback.data.split("_")[2]
    data = await state.get_data()
    place_id = data.get('place_id')
    if not place_id:
        return await callback.answer("Ошибка сессии", show_alert=True)

    if duration == "7":
        until = datetime.now() + timedelta(days=7)
    elif duration == "30":
        until = datetime.now() + timedelta(days=30)
    else:
        until = None

    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE fishing_places SET is_premium = ($1 IS NOT NULL), premium_until = $1 WHERE id = $2",
            until, place_id
        )

    status = "активирован" if until else "снят"
    await callback.message.answer(
        f"✅ *Премиум-статус для места #{place_id} {status}!*",
        parse_mode="Markdown",
        reply_markup=get_admin_main_keyboard()
    )
    await state.clear()
    await callback.answer()


@router.callback_query(AdminFieldCB.filter())
async def admin_edit_field(callback: CallbackQuery, callback_data: AdminFieldCB, state: FSMContext):
    await state.update_data(field=callback_data.field, place_id=callback_data.place_id)
    field_names = {
        "title": "название",
        "description": "описание",
        "price": "цену (число)",
        "link": "ссылку на сайт",
        "phone": "номер телефона",
        "images": "ссылки на фото (через запятую)"
    }
    field_name = field_names.get(callback_data.field, callback_data.field)
    await callback.message.answer(
        f"✏️ *Введите новое {field_name}*\n\n✖️ Напишите `-` для отмены",
        parse_mode="Markdown",
        reply_markup=None
    )
    await state.set_state(EditPlace.value)
    await callback.answer()


@router.message(EditPlace.value)
async def admin_edit_save(message: Message, state: FSMContext):
    data = await state.get_data()
    if message.text.strip() == "-":
        await message.answer("❌ Отменено", reply_markup=get_admin_main_keyboard())
        await state.clear()
        return
    field_map = {
        "title": "title",
        "description": "description",
        "price": "price_from",
        "link": "link_url",
        "phone": "phone",
        "images": "images"
    }
    db_field = field_map.get(data['field'])
    if not db_field:
        await message.answer("❌ Неверное поле", reply_markup=get_admin_main_keyboard())
        await state.clear()
        return
    try:
        value = float(message.text.replace(",", ".")) if db_field == "price_from" else (
            [img.strip() for img in message.text.split(',')] if db_field == "images" else message.text.strip()
        )
        async with db_pool.acquire() as conn:
            await conn.execute(
                f"UPDATE fishing_places SET {db_field} = $1 WHERE id = $2",
                value, data['place_id']
            )
        await message.answer(
            f"✅ *{data['field'].capitalize()} обновлено!*",
            parse_mode="Markdown",
            reply_markup=get_admin_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка обновления: {e}")
        await message.answer(f"❌ Ошибка: {e}")
    finally:
        await state.clear()


@router.callback_query(AdminPlaceCB.filter(F.action == "toggle_status"))
async def admin_toggle_status(callback: CallbackQuery, callback_data: AdminPlaceCB):
    try:
        async with db_pool.acquire() as conn:
            current_status = await conn.fetchval(
                "SELECT is_active FROM fishing_places WHERE id = $1",
                callback_data.place_id
            )
            await conn.execute(
                "UPDATE fishing_places SET is_active = $1 WHERE id = $2",
                not current_status, callback_data.place_id
            )
        new_status = "✅ активным" if not current_status else "❌ скрытым"
        await callback.answer(f"Место #{callback_data.place_id} сделано {new_status}", show_alert=True)
        await admin_edit_select(callback, callback_data, state=FSMContext())
    except Exception as e:
        logger.error(f"Ошибка переключения статуса: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)
    await callback.answer()


@router.callback_query(AdminPlaceCB.filter(F.action == "delete"))
async def admin_delete_confirm(callback: CallbackQuery, callback_data: AdminPlaceCB):
    try:
        async with db_pool.acquire() as conn:
            place = await conn.fetchval(
                "SELECT title FROM fishing_places WHERE id = $1",
                callback_data.place_id
            )
        if not place:
            return await callback.answer("❌ Место не найдено", show_alert=True)
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Да, удалить",
                       callback_data=AdminPlaceCB(action="confirm_delete", place_id=callback_data.place_id).pack())
        builder.button(text="❌ Нет, отмена", callback_data="admin_manage")
        builder.adjust(2)
        await callback.message.edit_text(
            f"⚠️ *Подтвердите удаление*\n\nМесто: *{place}*\nID: #{callback_data.place_id}\n\nЭто действие необратимо!",
            parse_mode="Markdown",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logger.error(f"Ошибка подтверждения удаления: {e}")
    await callback.answer()


@router.callback_query(AdminPlaceCB.filter(F.action == "confirm_delete"))
async def admin_delete_process(callback: CallbackQuery, callback_data: AdminPlaceCB):
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("DELETE FROM fishing_places WHERE id = $1", callback_data.place_id)
        await callback.message.edit_text(
            f"✅ *Место #{callback_data.place_id} успешно удалено!*",
            parse_mode="Markdown",
            reply_markup=get_admin_main_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка удаления: {e}")
        await callback.message.edit_text(
            f"❌ *Ошибка при удалении:*\n{e}",
            parse_mode="Markdown",
            reply_markup=get_admin_main_keyboard()
        )
    await callback.answer()


@router.callback_query(F.data == "admin_reviews")
async def admin_reviews(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer("⛔ Нет доступа", show_alert=True)
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT r.id, r.rating, r.comment, r.status, r.created_at, u.first_name, u.username, fp.title as place_name, fp.id as place_id, r.region_code, r.category_code FROM reviews r LEFT JOIN users u ON r.telegram_id = u.telegram_id LEFT JOIN fishing_places fp ON r.place_id = fp.id ORDER BY r.created_at DESC LIMIT 20"
            )
        if not rows:
            text = "📭 *Отзывов пока нет*"
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            builder.button(text="🔙 Назад", callback_data="admin_main")
        else:
            text = "⭐ *Последние отзывы (20):*\n\n"
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            builder = InlineKeyboardBuilder()
            for r in rows:
                user_name = r['first_name'] or r['username'] or f"ID:{r['telegram_id']}"
                place_name = r['place_name'] or "Не указано"
                region = REGIONS.get(r['region_code'], r['region_code']) if r['region_code'] else ""
                status_emoji = {"approved": "✅", "pending": "⏳", "rejected": "❌"}.get(r['status'], "")
                comment_preview = (r['comment'][:60] + "...") if len(r['comment']) > 60 else r['comment']
                text += f"{status_emoji} *{r['rating']}⭐ от {user_name}*\n {place_name} ({region})\n💬 {comment_preview}\n🕒 {r['created_at'].strftime('%d.%m.%Y %H:%M')}\n\n"
                if r['place_id']:
                    builder.button(text=f"📍 Место #{r['place_id']}",
                                   callback_data=AdminPlaceCB(action="edit", place_id=r['place_id']).pack())
            builder.button(text="🔙 Назад", callback_data="admin_main")
            builder.adjust(2)
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    except Exception as e:
        logger.error(f"Ошибка загрузки отзывов: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return await callback.answer(" Нет доступа", show_alert=True)
    try:
        async with db_pool.acquire() as conn:
            total_places = await conn.fetchval("SELECT COUNT(*) FROM fishing_places")
            active_places = await conn.fetchval("SELECT COUNT(*) FROM fishing_places WHERE is_active = TRUE")
            premium_places = await conn.fetchval("SELECT COUNT(*) FROM fishing_places WHERE is_premium = TRUE")
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
            total_reviews = await conn.fetchval("SELECT COUNT(*) FROM reviews")
            total_favorites = await conn.fetchval("SELECT COUNT(*) FROM favorites")
            region_stats = await conn.fetch(
                "SELECT r.name, COUNT(fp.id) as count FROM regions r LEFT JOIN fishing_places fp ON r.code = fp.region_code AND fp.is_active = TRUE GROUP BY r.code, r.name ORDER BY count DESC")
            top_places = await conn.fetch(
                "SELECT title, avg_rating, reviews_count FROM fishing_places WHERE is_active = TRUE AND reviews_count > 0 ORDER BY avg_rating DESC, reviews_count DESC LIMIT 5")
            active_users_week = await conn.fetchval(
                "SELECT COUNT(DISTINCT telegram_id) FROM reviews WHERE created_at > NOW() - INTERVAL '7 days'")

        text = "📊 *Статистика бота:*\n\n"
        text += f"📍 *Места:* {active_places}/{total_places} (активных/всего)\n"
        text += f"👑 *Премиум места:* {premium_places}\n"
        text += f"👥 *Пользователи:* {total_users}\n⭐ *Отзывы:* {total_reviews}\n❤️ *Избранное:* {total_favorites}\n🔥 *Активны за неделю:* {active_users_week}\n\n"
        text += "📍 *По регионам:*\n"
        for stat in region_stats[:5]:
            text += f"  • {stat['name']}: {stat['count']}\n"
        if top_places:
            text += "\n🏆 *Топ-5 по рейтингу:*\n"
            for i, place in enumerate(top_places, 1):
                text += f"  {i}. {place['title']} ({place['avg_rating']:.1f}⭐)\n"
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Обновить", callback_data="admin_stats")
        builder.button(text="🔙 Назад", callback_data="admin_main")
        builder.adjust(2)
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=builder.as_markup())
    except Exception as e:
        logger.error(f"Ошибка статистики: {e}")
        await callback.answer(" Ошибка загрузки статистики", show_alert=True)
    await callback.answer()


@router.callback_query(F.data == "admin_cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("❌ *Отменено*", parse_mode="Markdown", reply_markup=get_admin_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_main")
async def admin_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "⚙️ *Админ-панель*\n\nВыберите действие:",
        parse_mode="Markdown",
        reply_markup=get_admin_main_keyboard()
    )
    await callback.answer()