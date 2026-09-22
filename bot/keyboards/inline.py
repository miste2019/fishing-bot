from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
from bot.config import REGIONS, CATEGORIES, PUTEVKA_REGIONS

class CategoryCB(CallbackData, prefix="cat"):
    region: str
    category: str

class ReviewCB(CallbackData, prefix="review"):
    region: str
    category: str
    place_id: int | None = None

class FavoriteCB(CallbackData, prefix="fav"):
    action: str
    place_id: int

class AdminPlaceCB(CallbackData, prefix="admin_place"):
    action: str
    place_id: int

class AdminFieldCB(CallbackData, prefix="admin_field"):
    field: str
    place_id: int

def get_region_keyboard(region_code: str):
    builder = InlineKeyboardBuilder()
    for cat_code, cat_name in CATEGORIES.items():
        if cat_code == "putevka" and region_code not in PUTEVKA_REGIONS:
            continue
        builder.button(
            text=cat_name,
            callback_data=CategoryCB(region=region_code, category=cat_code).pack()
        )
    builder.button(text="🔙 Назад к регионам", callback_data="back_to_regions")
    builder.adjust(1)
    return builder.as_markup()

def get_admin_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить место", callback_data="admin_add")
    builder.button(text="📋 Управление местами", callback_data="admin_manage")
    builder.button(text="⭐ Отзывы", callback_data="admin_reviews")
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.adjust(2)
    return builder.as_markup()

def get_rating_keyboard():
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.button(text=f"{i} ⭐", callback_data=f"rating_{i}")
    builder.adjust(5)
    return builder.as_markup()