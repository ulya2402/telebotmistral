from aiogram import Bot, Dispatcher
from json_i18n_service import JsonI18n 
from config import TELEGRAM_BOT_TOKEN, LOCALES_DIR, DEFAULT_LANGUAGE 

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()


i18n = JsonI18n(path=LOCALES_DIR, default_locale=DEFAULT_LANGUAGE)
