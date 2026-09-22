from aiogram.utils.keyboard import ReplyKeyboardBuilder
from bot.config import REGIONS

def get_start_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text=" Справочник рыбака")
    builder.button(text="📍 Меню регионов")
    builder.button(text="❤️ Избранное")
    builder.button(text="👑 Премиум")
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)

def get_main_menu_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="🔙 Назад в главное меню")
    for name in REGIONS.values():
        builder.button(text=name)
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)