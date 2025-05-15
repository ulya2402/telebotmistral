import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

DEFAULT_MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-large-latest") 

AVAILABLE_MISTRAL_MODELS = {
    "mistral-large-latest": "Mistral Large",
    "mistral-medium-latest": "Mistral Medium",
    "mistral-small-latest": "Mistral Small",
    "mistral-saba-latest": "Mistral Saba",
    "codestral-latest": "Codestral",
}

if DEFAULT_MISTRAL_MODEL not in AVAILABLE_MISTRAL_MODELS:
    AVAILABLE_MISTRAL_MODELS[DEFAULT_MISTRAL_MODEL] = f"Default ({DEFAULT_MISTRAL_MODEL.replace('-latest', '').capitalize()})"


if not TELEGRAM_BOT_TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN tidak ditemukan di .env")
    raise ValueError("TELEGRAM_BOT_TOKEN tidak ditemukan di .env. Mohon periksa file .env Anda.")

if not MISTRAL_API_KEY:
    print("ERROR: MISTRAL_API_KEY tidak ditemukan di .env")
    raise ValueError("MISTRAL_API_KEY tidak ditemukan di .env. Mohon periksa file .env Anda.")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCALES_DIR = os.path.join(CURRENT_DIR, "locales")

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ["en", "id", "ru"]

MISTRAL_SYSTEM_PROMPT = os.getenv("MISTRAL_SYSTEM_PROMPT", None) 

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

MAX_HISTORY_MESSAGES = 10 

if not (SUPABASE_URL and SUPABASE_SERVICE_KEY):
    print("PERINGATAN: SUPABASE_URL atau SUPABASE_SERVICE_KEY tidak ditemukan di .env. Fitur riwayat percakapan tidak akan aktif.")
