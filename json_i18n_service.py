import json
import os
import logging
from typing import Dict, Optional, Any, Iterator 
from contextvars import ContextVar
from contextlib import contextmanager 

class JsonI18n:
    def __init__(self, path: str, default_locale: str = "en"):
        self.path = path
        self.default_locale = default_locale
        self.locales_data: Dict[str, Dict[str, str]] = {}
        self._load_translations()

        self.context_locale: ContextVar[str] = ContextVar("json_i18n_context_locale", default=self.default_locale)
        logging.info(f"JsonI18n initialized. Default locale: '{self.default_locale}'. Loaded locales: {list(self.locales_data.keys())}")

    def _load_translations(self):
        if not os.path.isdir(self.path):
            logging.error(f"Direktori locales '{self.path}' tidak ditemukan.")
            return

        for filename in os.listdir(self.path):
            if filename.endswith(".json"):
                locale_code = filename[:-5]
                file_path = os.path.join(self.path, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        self.locales_data[locale_code] = json.load(f)
                    logging.info(f"Berhasil memuat terjemahan untuk locale: {locale_code} dari {filename}")
                except json.JSONDecodeError as e:
                    logging.error(f"Error saat mendekode JSON untuk locale {locale_code} dari {filename}: {e}")
                except Exception as e:
                    logging.error(f"Error saat memuat file {filename}: {e}")

    @property
    def current_locale(self) -> str:
        return self.context_locale.get()

    def gettext(self, key: str, default: Optional[str] = None, locale_override: Optional[str] = None, **kwargs: Any) -> str:
        loc_to_use = locale_override if locale_override else self.current_locale
        lang_data = self.locales_data.get(loc_to_use)

        if not lang_data and loc_to_use != self.default_locale:
            logging.warning(f"Data locale '{loc_to_use}' tidak ditemukan, fallback ke default '{self.default_locale}' untuk kunci '{key}'.")
            lang_data = self.locales_data.get(self.default_locale)

        if not lang_data:
            logging.error(f"Tidak ada data terjemahan (termasuk default) yang ditemukan untuk kunci '{key}'. Menggunakan fallback.")
            return default if default is not None else key

        translated_string = lang_data.get(key)

        if translated_string is None:
            if loc_to_use != self.default_locale:
                default_lang_data = self.locales_data.get(self.default_locale)
                if default_lang_data:
                    translated_string = default_lang_data.get(key)

            if translated_string is None:
                logging.warning(f"Kunci '{key}' tidak ditemukan di locale '{loc_to_use}' atau di default locale. Menggunakan fallback.")
                return default if default is not None else key

        try:
            return translated_string.format(**kwargs) if kwargs else translated_string
        except KeyError as e:
            logging.warning(f"Placeholder {e} hilang untuk kunci '{key}' di locale '{loc_to_use}' dengan kwargs {kwargs}. Mengembalikan string tanpa format.")
            return translated_string
        except Exception as e:
            logging.error(f"Error saat memformat string untuk kunci '{key}': {e}. Mengembalikan string tanpa format.")
            return translated_string

    @contextmanager # Dekorator untuk menjadikan metode ini context manager
    def use_locale(self, locale: str) -> Iterator['JsonI18n']: # Mengembalikan instance dirinya sendiri
        """
        Context manager untuk menggunakan locale tertentu secara sementara.
        """
        if locale not in self.locales_data and locale != self.default_locale:
            logging.warning(f"Mencoba menggunakan locale sementara '{locale}' yang tidak ada datanya.")

        token = self.context_locale.set(locale)
        try:
            yield self # Mengembalikan instance agar bisa digunakan jika perlu (meski biasanya tidak)
        finally:
            self.context_locale.reset(token)

    @contextmanager 
    def context(self) -> Iterator[None]:
        """
        Context manager yang dibutuhkan oleh I18nMiddleware.
        Biasanya digunakan untuk setup/cleanup per event, di sini kita biarkan kosong.
        """
        try:
            yield
        finally:
            pass 
