import logging
from typing import Dict, Any 
from aiogram import types, F
from aiogram.filters import CommandStart, Command 
from aiogram.filters.command import CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode, ChatType 
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot_setup import dp, i18n, bot 
from config import (
    SUPPORTED_LANGUAGES, 
    MISTRAL_SYSTEM_PROMPT, 
    DEFAULT_MISTRAL_MODEL,
    AVAILABLE_MISTRAL_MODELS,
    DEFAULT_LANGUAGE
)
from mistral_integration import get_mistral_client
from markdown_utils import ensure_valid_markdown
from supabase_service import (
    is_supabase_enabled,
    get_current_session_id,
    start_new_chat_session,
    add_message_to_history,
    get_conversation_history,
    get_user_language_preference,
    set_user_language_preference,
    get_user_model_preference,
    set_user_model_preference
)

LANGUAGE_NAMES = { "en": "English 🇬🇧", "id": "Indonesia 🇮🇩", "ru": "Русский 🇷🇺", "fr": "Français 🇫🇷" }

def get_language_keyboard_builder() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for lang_code, lang_name in LANGUAGE_NAMES.items():
        if lang_code in SUPPORTED_LANGUAGES:
            builder.row(InlineKeyboardButton(text=lang_name, callback_data=f"setlang_{lang_code}"))
    return builder

def get_model_keyboard_builder(current_model_id: str) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for model_id, display_name in AVAILABLE_MISTRAL_MODELS.items():
        text = f"✅ {display_name}" if model_id == current_model_id else display_name
        builder.row(InlineKeyboardButton(text=text, callback_data=f"setmodel_{model_id}"))
    builder.row(InlineKeyboardButton(text=i18n.gettext("back_to_settings_button", default="⬅️ Back to Settings"), callback_data="settings_main"))
    return builder

def get_main_settings_keyboard_builder() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=i18n.gettext("change_language_button", default="🌐 Change Language"), callback_data="settings_change_language"))
    builder.row(InlineKeyboardButton(text=i18n.gettext("change_model_button", default="🤖 Change AI Model"), callback_data="settings_change_model"))
    return builder

@dp.message(CommandStart(), F.chat.type == ChatType.PRIVATE)
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    logging.info(f"User {user_id} mengirim perintah /start.")
    welcome_text = i18n.gettext(key="welcome_message") 
    await message.reply(welcome_text, parse_mode=ParseMode.MARKDOWN)
    if is_supabase_enabled():
        await get_current_session_id(user_id, auto_create=True)

@dp.message(Command("help")) 
async def help_command_handler(message: types.Message, **workflow_data: Dict[str, Any]):
    user_id = message.from_user.id
    bot_username = workflow_data.get("bot_username") 
    logging.info(f"User {user_id} meminta /help di chat {message.chat.id}.")

    
    current_lang_code = DEFAULT_LANGUAGE
    if is_supabase_enabled():
        db_lang = await get_user_language_preference(user_id)
        if db_lang and db_lang in SUPPORTED_LANGUAGES:
            current_lang_code = db_lang

    help_text_key = "help_message_text"
    add_to_group_button_key = "add_to_group_button"
    official_chat_button_key = "official_mistral_chat_button"

    help_text_translated = ""
    add_to_group_button_text = ""
    official_chat_button_text = ""

    
    with i18n.use_locale(current_lang_code):
        
        bot_username_for_display = bot_username if bot_username else "NamaBotSaya" 
        help_text_translated = i18n.gettext(help_text_key).format(bot_username=bot_username_for_display)
        add_to_group_button_text = i18n.gettext(add_to_group_button_key)
        official_chat_button_text = i18n.gettext(official_chat_button_key)

    builder = InlineKeyboardBuilder()
    if bot_username: 
        add_to_group_url = f"https://t.me/{bot_username}?startgroup=true&admin=change_info+delete_messages+invite_users" 
        builder.row(InlineKeyboardButton(text=add_to_group_button_text, url=add_to_group_url))

    builder.row(InlineKeyboardButton(text=official_chat_button_text, url="https://chat.mistral.ai/chat"))


    await message.reply(help_text_translated, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)


@dp.message(Command("language", "lang")) 
async def language_command_handler(message: types.Message):
    user_id = message.from_user.id 
    logging.info(f"User {user_id} meminta pilihan bahasa dengan perintah /language atau /lang di chat {message.chat.id}.")
    db_lang = None
    if is_supabase_enabled(): db_lang = await get_user_language_preference(user_id)
    user_locale = db_lang or DEFAULT_LANGUAGE
    prompt_text = ""
    with i18n.use_locale(user_locale): prompt_text = i18n.gettext("select_language_button_prompt")
    keyboard = get_language_keyboard_builder().as_markup()
    
    await message.reply(prompt_text, reply_markup=keyboard)



@dp.message(Command("settings")) 
async def settings_command_handler(message: types.Message):
    user_id = message.from_user.id # Pengaturan tetap per pengguna
    logging.info(f"User {user_id} mengakses /settings di chat {message.chat.id}.")

    current_lang_code = (await get_user_language_preference(user_id) if is_supabase_enabled() else None) or DEFAULT_LANGUAGE
    current_model_id = (await get_user_model_preference(user_id) if is_supabase_enabled() else None) or DEFAULT_MISTRAL_MODEL

    current_lang_name = LANGUAGE_NAMES.get(current_lang_code, current_lang_code)
    current_model_name = AVAILABLE_MISTRAL_MODELS.get(current_model_id, current_model_id)

    if current_model_id not in AVAILABLE_MISTRAL_MODELS and (await get_user_model_preference(user_id) if is_supabase_enabled() else None):
        old_model_pref = await get_user_model_preference(user_id) # Ambil model lama untuk pesan
        logging.warning(f"Model tersimpan user {user_id} '{old_model_pref}' tidak ada di daftar. Kembali ke default.")
        current_model_id = DEFAULT_MISTRAL_MODEL 
        if is_supabase_enabled(): await set_user_model_preference(user_id, DEFAULT_MISTRAL_MODEL)
        current_model_name = AVAILABLE_MISTRAL_MODELS.get(current_model_id, current_model_id)
        with i18n.use_locale(current_lang_code):
            # Kirim sebagai pesan baru jika yang asli dari perintah /settings
            await message.answer(i18n.gettext("model_not_found_in_list").format(model_name=old_model_pref))

    text = ""; keyboard = None
    with i18n.use_locale(current_lang_code):
        text = i18n.gettext("settings_menu_title") + "\n\n"
        text += i18n.gettext("current_language_label").format(current_lang_name=current_lang_name) + "\n"
        text += i18n.gettext("current_model_label").format(current_model_name=current_model_name)
        keyboard = get_main_settings_keyboard_builder().as_markup()

    await message.reply(text, reply_markup=keyboard)


@dp.message(Command("newchat"))
async def new_chat_command_handler(message: types.Message):
    user_id = message.from_user.id 
    logging.info(f"User {user_id} meminta sesi chat baru dengan /newchat di chat {message.chat.id}.")
    if not is_supabase_enabled():
        await message.reply(i18n.gettext("feature_supabase_unavailable"))
        return
    new_session_id = await start_new_chat_session(user_id, delete_previous_messages=True) 
    if new_session_id:
        await message.reply(i18n.gettext("new_chat_session_started"))
        logging.info(f"User {user_id} memulai sesi chat baru: {new_session_id}. Pesan lama dihapus.")
    else:
        await message.reply(i18n.gettext("internal_error_message"))

@dp.callback_query(F.data.startswith("setlang_"))
async def process_language_callback(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    lang_code = callback_query.data.split("_", 1)[1] 
    if lang_code in SUPPORTED_LANGUAGES:
        if is_supabase_enabled(): await set_user_language_preference(user_id, lang_code)
        lang_name = LANGUAGE_NAMES.get(lang_code, lang_code)
        confirmation_text = ""; settings_text = ""; keyboard = None
        with i18n.use_locale(lang_code): 
            confirmation_text = i18n.gettext("language_set_message").format(language_name=lang_name)
            current_model_id = (await get_user_model_preference(user_id) if is_supabase_enabled() else None) or DEFAULT_MISTRAL_MODEL
            current_model_name = AVAILABLE_MISTRAL_MODELS.get(current_model_id, current_model_id)
            settings_text = i18n.gettext("settings_menu_title") + "\n\n"
            settings_text += i18n.gettext("current_language_label").format(current_lang_name=lang_name) + "\n" 
            settings_text += i18n.gettext("current_model_label").format(current_model_name=current_model_name)
            keyboard = get_main_settings_keyboard_builder().as_markup()
        try:
            if callback_query.message:
                 await callback_query.message.edit_text(settings_text, reply_markup=keyboard)
                 await callback_query.answer(text=confirmation_text, show_alert=False)
        except Exception as e:
            logging.warning(f"Tidak bisa mengedit pesan untuk konfirmasi bahasa user {user_id}: {e}")
            if callback_query.message: await callback_query.message.answer(confirmation_text, parse_mode=ParseMode.MARKDOWN)
            else: await bot.send_message(user_id, confirmation_text, parse_mode=ParseMode.MARKDOWN) # Menggunakan objek bot global
            await callback_query.answer()
        logging.info(f"User {user_id} mengatur bahasa ke {lang_code} via tombol (DB: {is_supabase_enabled()}).")
    else:
        await callback_query.answer(text="Error: Bahasa yang dipilih tidak didukung.", show_alert=True)
        logging.error(f"User {user_id} memilih bahasa yg tidak didukung via callback: {lang_code}")

@dp.callback_query(F.data == "settings_change_language")
async def cq_settings_change_language(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    db_lang = None
    if is_supabase_enabled(): db_lang = await get_user_language_preference(user_id)
    user_locale = db_lang or DEFAULT_LANGUAGE
    prompt_text = ""; keyboard_builder = None
    with i18n.use_locale(user_locale):
        prompt_text = i18n.gettext("select_language_button_prompt")
        keyboard_builder = get_language_keyboard_builder()
        keyboard_builder.row(InlineKeyboardButton(text=i18n.gettext("back_to_settings_button"), callback_data="settings_main"))
    if callback_query.message: await callback_query.message.edit_text(prompt_text, reply_markup=keyboard_builder.as_markup())
    await callback_query.answer()

@dp.callback_query(F.data == "settings_change_model")
async def cq_settings_change_model(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    current_model_id = (await get_user_model_preference(user_id) if is_supabase_enabled() else None) or DEFAULT_MISTRAL_MODEL
    if current_model_id not in AVAILABLE_MISTRAL_MODELS: current_model_id = DEFAULT_MISTRAL_MODEL
    user_locale = (await get_user_language_preference(user_id) if is_supabase_enabled() else None) or DEFAULT_LANGUAGE
    prompt_text = ""; keyboard = None
    with i18n.use_locale(user_locale):
        prompt_text = i18n.gettext("select_model_prompt")
        keyboard = get_model_keyboard_builder(current_model_id).as_markup()
    if callback_query.message: await callback_query.message.edit_text(prompt_text, reply_markup=keyboard)
    await callback_query.answer()

@dp.callback_query(F.data.startswith("setmodel_"))
async def cq_set_model(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    model_id = callback_query.data.split("_", 1)[1]
    if model_id in AVAILABLE_MISTRAL_MODELS:
        if is_supabase_enabled(): await set_user_model_preference(user_id, model_id)
        model_name_display = AVAILABLE_MISTRAL_MODELS.get(model_id, model_id)
        user_locale = (await get_user_language_preference(user_id) if is_supabase_enabled() else None) or DEFAULT_LANGUAGE
        confirmation_text = ""; settings_text = ""; keyboard = None
        with i18n.use_locale(user_locale):
            confirmation_text = i18n.gettext("model_set_message").format(model_name=model_name_display)
            current_lang_name = LANGUAGE_NAMES.get(user_locale, user_locale)
            settings_text = i18n.gettext("settings_menu_title") + "\n\n"
            settings_text += i18n.gettext("current_language_label").format(current_lang_name=current_lang_name) + "\n"
            settings_text += i18n.gettext("current_model_label").format(current_model_name=model_name_display)
            keyboard = get_main_settings_keyboard_builder().as_markup()
        await callback_query.answer(text=confirmation_text, show_alert=False)
        if callback_query.message: await callback_query.message.edit_text(settings_text, reply_markup=keyboard)
        logging.info(f"User {user_id} mengatur model AI ke {model_id} (DB: {is_supabase_enabled()}).")
    else:
        await callback_query.answer("Error: Model tidak valid.", show_alert=True)
        logging.error(f"User {user_id} mencoba mengatur model tidak valid: {model_id}")

@dp.callback_query(F.data == "settings_main")
async def cq_settings_main_menu(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    current_lang_code = (await get_user_language_preference(user_id) if is_supabase_enabled() else None) or DEFAULT_LANGUAGE
    current_model_id = (await get_user_model_preference(user_id) if is_supabase_enabled() else None) or DEFAULT_MISTRAL_MODEL
    if current_model_id not in AVAILABLE_MISTRAL_MODELS:
        current_model_id = DEFAULT_MISTRAL_MODEL
        if is_supabase_enabled(): await set_user_model_preference(user_id, DEFAULT_MISTRAL_MODEL)
    text = ""; keyboard = None
    with i18n.use_locale(current_lang_code):
        current_lang_name = LANGUAGE_NAMES.get(current_lang_code, current_lang_code)
        current_model_name = AVAILABLE_MISTRAL_MODELS.get(current_model_id, current_model_id)
        text = i18n.gettext("settings_menu_title") + "\n\n"
        text += i18n.gettext("current_language_label").format(current_lang_name=current_lang_name) + "\n"
        text += i18n.gettext("current_model_label").format(current_model_name=current_model_name)
        keyboard = get_main_settings_keyboard_builder().as_markup()
    if callback_query.message: await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


async def process_prompt_to_mistral(message: types.Message, user_prompt: str, from_user_id: int, workflow_data: Dict[str, Any]):
    
    mistral_api_client = get_mistral_client()
    if not mistral_api_client:
        logging.error(f"Klien Mistral tidak tersedia untuk user {from_user_id}.")
        user_locale_err = (await get_user_language_preference(from_user_id) if is_supabase_enabled() else None) or DEFAULT_LANGUAGE
        with i18n.use_locale(user_locale_err):
            await message.reply(i18n.gettext("mistral_client_not_initialized_error"), parse_mode=ParseMode.MARKDOWN)
        return

    selected_model_id = (await get_user_model_preference(from_user_id) if is_supabase_enabled() else None) or DEFAULT_MISTRAL_MODEL
    if selected_model_id not in AVAILABLE_MISTRAL_MODELS:
        logging.warning(f"Model pilihan user {from_user_id} '{selected_model_id}' tidak lagi tersedia. Menggunakan default: {DEFAULT_MISTRAL_MODEL}")
        selected_model_id = DEFAULT_MISTRAL_MODEL
        if is_supabase_enabled(): await set_user_model_preference(from_user_id, selected_model_id)

    current_session_id: Optional[str] = None
    conversation_history_for_api: List[Dict[str, str]] = []
    if is_supabase_enabled():
        current_session_id = await get_current_session_id(from_user_id, auto_create=True)
        if current_session_id:
            await add_message_to_history(from_user_id, current_session_id, "user", user_prompt)
            conversation_history_for_api = await get_conversation_history(from_user_id, current_session_id)
        else: logging.warning(f"Tidak bisa mendapatkan/membuat session_id untuk user {from_user_id}. Melanjutkan tanpa riwayat.")
    api_messages: List[Dict[str, str]] = []
    if MISTRAL_SYSTEM_PROMPT: api_messages.append({"role": "system", "content": MISTRAL_SYSTEM_PROMPT})
    if conversation_history_for_api: api_messages.extend(conversation_history_for_api)
    else: api_messages.append({"role": "user", "content": user_prompt})
    processing_message = None
    try:
        processing_message = await message.reply(i18n.gettext("thinking_message"))
        logging.info(f"Mengirim permintaan ke Mistral AI model '{selected_model_id}' untuk user {from_user_id} (session: {current_session_id}) dengan {len(api_messages)} pesan.")
        chat_response = mistral_api_client.chat.complete(model=selected_model_id, messages=api_messages)
        if chat_response.choices:
            mistral_reply_raw = chat_response.choices[0].message.content
            if is_supabase_enabled() and current_session_id:
                await add_message_to_history(from_user_id, current_session_id, "assistant", mistral_reply_raw)
            mistral_reply_markdown_safe = ensure_valid_markdown(mistral_reply_raw)
            logging.info(f"Menerima balasan (raw) dari Mistral AI untuk user {from_user_id}: '{mistral_reply_raw[:70]}...'")
            await processing_message.edit_text(mistral_reply_markdown_safe,parse_mode=ParseMode.MARKDOWN,disable_web_page_preview=True)
        else:
            logging.warning(f"Respons Mistral AI untuk user {from_user_id} tidak memiliki pilihan (choices).")
            await processing_message.edit_text(i18n.gettext("mistral_no_response_error"), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logging.error(f"Error saat memproses pesan dari user {from_user_id} dengan Mistral AI: {e}", exc_info=True)
        error_reply_key = "internal_error_message"; error_params = {}
        error_str = str(e).lower()
        if "model_not_found" in error_str or ("No such model" in str(e) and hasattr(e, "response") and e.response.status_code == 404):
             error_reply_key = "model_not_found_error_message"; error_params = {"model_name": selected_model_id}
        elif "authentication" in error_str or "api key" in error_str or "invalid api key" in error_str: error_reply_key = "api_key_error_message"
        elif "rate limit" in error_str or ("429" in str(e) and "exceeded" in error_str): error_reply_key = "rate_limit_error_message"
        elif "insufficient_quota" in error_str: error_reply_key = "insufficient_quota_error_message"
        user_locale_for_error = (await get_user_language_preference(from_user_id) if is_supabase_enabled() else None) or DEFAULT_LANGUAGE
        final_error_reply_raw = ""
        with i18n.use_locale(user_locale_for_error):
            final_error_reply_raw = i18n.gettext(error_reply_key)
            if error_params: final_error_reply_raw = final_error_reply_raw.format(**error_params)
        final_error_reply_safe = ensure_valid_markdown(final_error_reply_raw)
        if processing_message:
            try: await processing_message.edit_text(final_error_reply_safe, parse_mode=ParseMode.MARKDOWN)
            except Exception as edit_exc:
                logging.error(f"Gagal mengedit pesan proses untuk user {from_user_id}: {edit_exc}")
                await message.reply(final_error_reply_safe, parse_mode=ParseMode.MARKDOWN)
        else: await message.reply(final_error_reply_safe, parse_mode=ParseMode.MARKDOWN)


@dp.message(F.chat.type == ChatType.PRIVATE, F.text) # Hanya proses jika ada F.text
async def handle_private_message(message: types.Message, **workflow_data: Dict[str, Any]): # Terima workflow_data
    await process_prompt_to_mistral(
        message=message, 
        user_prompt=message.text, # type: ignore (karena F.text memastikan message.text ada)
        from_user_id=message.from_user.id, 
        workflow_data=workflow_data
    )


@dp.message(Command("mistral"), F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def handle_group_mistral_command(message: types.Message, command: CommandObject, **workflow_data: Dict[str, Any]):
    user_id = message.from_user.id 
    if command.args:
        prompt = command.args.strip()
        logging.info(f"Perintah /mistral diterima di grup {message.chat.id} dari user {user_id} dengan prompt: '{prompt}'")
        await process_prompt_to_mistral(message=message, user_prompt=prompt, from_user_id=user_id, workflow_data=workflow_data)
    else:
        logging.info(f"Perintah /mistral diterima di grup {message.chat.id} dari user {user_id} tanpa argumen.")
        hint_text = i18n.gettext("group_command_usage_hint") # Locale akan diatur oleh middleware
        await message.reply(hint_text)


@dp.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.text) # Hanya proses jika ada F.text
async def handle_group_interaction(message: types.Message, **workflow_data: Dict[str, Any]):
    bot_username = workflow_data.get("bot_username")
    user_id = message.from_user.id 
    prompt = None
    interaction_type = None

    if not message.text: # Seharusnya tidak terjadi karena F.text, tapi untuk keamanan
        return 

    # 1. Cek Mention di awal
    if bot_username and message.text.lower().startswith(f"@{bot_username.lower()}"):
        prompt = message.text[len(bot_username) + 1:].strip() # +1 untuk @
        interaction_type = "mention"
        logging.info(f"Mention @{bot_username} diterima di grup {message.chat.id} dari user {user_id} dengan prompt: '{prompt}'")

    # 2. Cek Reply ke pesan Bot
    elif message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.username == bot_username:
        prompt = message.text.strip() # Anggap seluruh teks reply adalah prompt lanjutan
        interaction_type = "reply_to_bot"
        logging.info(f"Reply ke pesan bot diterima di grup {message.chat.id} dari user {user_id} dengan prompt: '{prompt}'")

    if prompt is not None: # Jika ada prompt dari mention atau reply
        if not prompt and interaction_type == "mention": # Mention kosong
            logging.info(f"Mention @{bot_username} diterima di grup {message.chat.id} dari user {user_id} tanpa prompt tambahan.")
            return

        await process_prompt_to_mistral(message=message, user_prompt=prompt, from_user_id=user_id, workflow_data=workflow_data)
 
