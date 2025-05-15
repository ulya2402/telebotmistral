import asyncio
import logging
import sys
from typing import Dict, Any, Optional 

from aiogram import types
from aiogram.types import TelegramObject
from aiogram.utils.i18n import I18nMiddleware

from bot_setup import bot, dp, i18n 
from mistral_integration import get_mistral_client
from config import SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE 
from supabase_service import get_user_language_preference, is_supabase_enabled


class CustomJsonI18nMiddleware(I18nMiddleware):
    async def get_locale(self, event: TelegramObject, data: Dict[str, Any]) -> str:
        user: Optional[types.User] = data.get("event_from_user")
        preferred_lang = None

        if user:
            user_id = user.id
            if is_supabase_enabled():
                db_lang = await get_user_language_preference(user_id)
                if db_lang and db_lang in SUPPORTED_LANGUAGES:
                    preferred_lang = db_lang

            if not preferred_lang and user.language_code:
                lang_code_short = user.language_code.split('-')[0] 
                if lang_code_short in SUPPORTED_LANGUAGES:
                    preferred_lang = lang_code_short

        return preferred_lang if preferred_lang else DEFAULT_LANGUAGE


async def main_polling():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)-8s - %(name)-15s - %(module)-20s:%(lineno)d - %(message)s",
        stream=sys.stdout,
        force=True
    )

    print("--- Bot script dimulai ---")
    logging.info("Konfigurasi logging diterapkan. Bot memulai...")

    # Ambil informasi bot, termasuk username
    try:
        bot_info = await bot.get_me()
        # Simpan username bot di workflow_data dispatcher agar bisa diakses di handler
        dp.workflow_data["bot_username"] = bot_info.username
        logging.info(f"Username bot: @{bot_info.username} telah disimpan.")
    except Exception as e:
        logging.critical(f"Gagal mendapatkan informasi bot (username): {e}. Mention handler mungkin tidak berfungsi.")
        dp.workflow_data["bot_username"] = None # Atau nama default jika ada

    import handlers.message_handlers 

    if not i18n.locales_data:
        logging.error(f"Tidak ada data terjemahan yang dimuat dari {i18n.path}. Periksa path dan file JSON.")
    else:
        logging.info(f"Data terjemahan berhasil dimuat untuk locales: {list(i18n.locales_data.keys())}")

    if not get_mistral_client():
        logging.critical("Klien Mistral AI tidak berhasil diinisialisasi...")

    if not is_supabase_enabled():
        logging.warning("Supabase tidak dikonfigurasi atau gagal diinisialisasi. Fitur berbasis database tidak akan berfungsi.")

    actual_i18n_middleware = CustomJsonI18nMiddleware(i18n=i18n)
    dp.update.outer_middleware.register(actual_i18n_middleware)

    logging.info("Memulai polling bot Telegram...")
    try:
        await dp.start_polling(bot)
    finally:
        logging.info("Polling bot dihentikan. Menutup sesi bot...")
        await bot.session.close()
        logging.info("Sesi bot telah ditutup.")


if __name__ == '__main__':
    try:
        asyncio.run(main_polling())
    except KeyboardInterrupt:
        print("\n--- Bot dihentikan secara manual (KeyboardInterrupt) ---")
        logging.info("Bot dihentikan secara manual.")
    except Exception as e:
        print(f"FATAL ERROR saat menjalankan bot: {e}")
        logging.critical(f"Error fatal saat menjalankan bot: {e}", exc_info=True)
