from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    bot_token: str
    database_url: str
    admin_ids: list[int]
    yandex_iam_token: str = ""
    yandex_folder_id: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()

REGIONS = {
    "msk": "🏙 Москва и МО",
    "karelia": "🌲 Карелия",
    "astrakhan": "🎣 Астрахань",
    "spb": "🏛 Санкт-Петербург",
    "krasnodar": "🌴 Краснодарский край",
    "rostov": "🌾 Ростов-на-Дону",
    "dagestan": "🏔 Дагестан",
    "baikal": "🏞 Байкал"
}

CATEGORIES = {
    "vip_fishing": "💎 VIP рыбалка",
    "base": "🏡 Базы отдыха",
    "shop": "🛒 Магазины",
    "wild": "🌲 Дикая рыбалка",
    "yacht": " Яхты и катера",
    "putevka": "🎫 Путёвки"
}

REVERSE_REGIONS = {v: k for k, v in REGIONS.items()}
PUTEVKA_REGIONS = ["karelia"]