import logging
import uuid
from typing import List, Dict, Optional, Any
from supabase import create_client, Client
from postgrest import APIResponse

from config import SUPABASE_URL, SUPABASE_SERVICE_KEY, MAX_HISTORY_MESSAGES, DEFAULT_LANGUAGE, DEFAULT_MISTRAL_MODEL

supabase_client: Optional[Client] = None

if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        logging.info("Klien Supabase berhasil diinisialisasi.")
    except Exception as e:
        logging.error(f"Gagal menginisialisasi klien Supabase: {e}")
        supabase_client = None
else:
    logging.warning("SUPABASE_URL atau SUPABASE_SERVICE_KEY tidak ada. Klien Supabase tidak diinisialisasi.")

def is_supabase_enabled() -> bool:
    return supabase_client is not None

def _is_supabase_response_error(operation_name: str, user_id: Optional[int], api_response: Optional[APIResponse], session_id: Optional[str] = None) -> bool:
    if not api_response:
        logging.error(f"Respons Supabase adalah None (kemungkinan error koneksi) saat {operation_name} untuk user {user_id}" + (f", session {session_id}" if session_id else ""))
        return True

    actual_error_obj = None
    if hasattr(api_response, 'error'):
        actual_error_obj = api_response.error

    status_code_val = 0 
    has_status_code_attr = hasattr(api_response, 'status_code')
    if has_status_code_attr:
        status_code_val = api_response.status_code
    else:
        if actual_error_obj is None: # Jika tidak ada error obj DAN tidak ada status code
            logging.debug(f"Supabase: Atribut status_code tidak ditemukan pada APIResponse (dan tidak ada error obj) untuk {operation_name} user {user_id}.")
            return False # Anggap sukses jika tidak ada error object yang jelas
        # Jika ada error obj tapi tidak ada status_code, tetap log error
        logging.warning(f"Supabase: Atribut status_code tidak ditemukan pada APIResponse untuk {operation_name} user {user_id} (ada error obj).")


    is_error = False
    if actual_error_obj is not None:
        is_error = True
    elif has_status_code_attr and not (200 <= status_code_val < 300):
        is_error = True

    if is_error:
        error_message = "Unknown Supabase error"
        status_code_to_log = status_code_val if has_status_code_attr else "N/A"

        if actual_error_obj:
            if hasattr(actual_error_obj, 'message') and actual_error_obj.message:
                error_message = actual_error_obj.message
            else:
                error_message = str(actual_error_obj)
        elif hasattr(api_response, 'data'):
            if isinstance(api_response.data, dict) and 'message' in api_response.data:
                error_message = api_response.data['message']
            elif api_response.data is not None:
                error_message = f"Operasi gagal dengan status {status_code_to_log}. Data: {str(api_response.data)[:150]}"
        else:
             error_message = f"Operasi gagal dengan status {status_code_to_log}."

        log_session_id_str = f", session {session_id}" if session_id else ""
        logging.error(
            f"Supabase error (status: {status_code_to_log}) saat {operation_name} untuk user {user_id}{log_session_id_str}: {error_message}"
        )
        return True 

    return False

# --- Fungsi untuk User Sessions dan Chat Messages (sudah ada, tidak diubah signifikan) ---
async def start_new_chat_session(user_id: int, delete_previous_messages: bool = False) -> Optional[str]:
    if not is_supabase_enabled():
        logging.warning(f"Supabase tidak aktif, tidak bisa memulai sesi baru untuk user {user_id}")
        return None
    old_session_id: Optional[str] = None
    if delete_previous_messages:
        try:
            session_response = supabase_client.table("user_sessions").select("current_session_id").eq("user_id", user_id).maybe_single().execute()
            if session_response and not _is_supabase_response_error("mengambil sesi lama (sebelum delete)", user_id, session_response):
                if isinstance(session_response.data, dict) and session_response.data.get("current_session_id"):
                    old_session_id = session_response.data["current_session_id"]
                    logging.info(f"Sesi lama {old_session_id} ditemukan untuk user {user_id}, akan dihapus pesannya.")
        except Exception as e:
            logging.error(f"Exception saat mengambil session_id lama untuk user {user_id} sebelum penghapusan: {e}", exc_info=True)
    new_session_id = str(uuid.uuid4())
    try:
        upsert_response = supabase_client.table("user_sessions").upsert({
            "user_id": user_id, "current_session_id": new_session_id, "updated_at": "now()" 
        }).execute()
        if _is_supabase_response_error("upsert sesi baru", user_id, upsert_response): return None
        logging.info(f"Berhasil memulai sesi chat baru {new_session_id} untuk user {user_id}")
        if old_session_id and delete_previous_messages:
            logging.info(f"Menghapus pesan dari sesi lama {old_session_id} untuk user {user_id}.")
            try:
                delete_msg_response = supabase_client.table("chat_messages").delete().eq("user_id", user_id).eq("session_id", old_session_id).execute()
                if _is_supabase_response_error("menghapus pesan lama", user_id, delete_msg_response, session_id=old_session_id):
                    logging.warning(f"Gagal menghapus semua pesan lama untuk sesi {old_session_id}, user {user_id}.")
                else: logging.info(f"Berhasil memicu penghapusan pesan dari sesi lama {old_session_id} untuk user {user_id}.")
            except Exception as e_del: logging.error(f"Exception saat menghapus pesan lama untuk user {user_id}, sesi {old_session_id}: {e_del}", exc_info=True)
        return new_session_id
    except Exception as e:
        logging.error(f"Exception umum saat memulai sesi chat baru untuk user {user_id}: {e}", exc_info=True)
        return None

async def get_current_session_id(user_id: int, auto_create: bool = True) -> Optional[str]:
    if not is_supabase_enabled():
        logging.warning(f"Supabase tidak aktif, tidak bisa mendapatkan sesi untuk user {user_id}")
        return None
    try:
        api_response = supabase_client.table("user_sessions").select("current_session_id").eq("user_id", user_id).maybe_single().execute()
        if not api_response: 
            logging.error(f"Menerima respons None dari Supabase saat query sesi user {user_id}.")
            return await start_new_chat_session(user_id, delete_previous_messages=False) if auto_create else None
        if _is_supabase_response_error("mendapatkan sesi saat ini", user_id, api_response):
            return await start_new_chat_session(user_id, delete_previous_messages=False) if auto_create else None
        if isinstance(api_response.data, dict) and api_response.data.get("current_session_id"):
            logging.debug(f"Sesi ID ditemukan untuk user {user_id}: {api_response.data['current_session_id']}")
            return api_response.data["current_session_id"]
        else: 
            if auto_create:
                logging.info(f"Tidak ada sesi aktif untuk user {user_id}, membuat sesi baru.")
                return await start_new_chat_session(user_id, delete_previous_messages=False)
            else:
                logging.debug(f"Tidak ada sesi aktif untuk user {user_id} dan auto_create adalah False.")
                return None
    except Exception as e:
        logging.error(f"Exception tak terduga saat mendapatkan session ID untuk user {user_id}: {e}", exc_info=True)
        return await start_new_chat_session(user_id, delete_previous_messages=False) if auto_create else None

async def add_message_to_history(user_id: int, session_id: str, role: str, content: str):
    if not is_supabase_enabled() or not session_id: return
    try:
        message_data = { "user_id": user_id, "session_id": session_id, "role": role, "content": content }
        api_response = supabase_client.table("chat_messages").insert(message_data).execute()
        if not _is_supabase_response_error("menambahkan pesan ke riwayat", user_id, api_response, session_id=session_id):
            logging.debug(f"Pesan ditambahkan ke riwayat untuk user {user_id}, session {session_id}")
    except Exception as e: logging.error(f"Exception saat menambahkan pesan ke riwayat untuk user {user_id}, session {session_id}: {e}", exc_info=True)

async def get_conversation_history(user_id: int, session_id: str) -> List[Dict[str, str]]:
    history: List[Dict[str, str]] = []
    if not is_supabase_enabled() or not session_id: return history
    try:
        api_response = (supabase_client.table("chat_messages").select("role, content")
            .eq("user_id", user_id).eq("session_id", session_id)
            .order("created_at", desc=True).limit(MAX_HISTORY_MESSAGES).execute())
        if not api_response or _is_supabase_response_error("mengambil riwayat", user_id, api_response, session_id=session_id): return history
        if api_response.data:
            for item in reversed(api_response.data): history.append({"role": item["role"], "content": item["content"]})
            logging.debug(f"Mengambil {len(history)} pesan dari riwayat untuk user {user_id}, session {session_id}")
        return history
    except Exception as e:
        logging.error(f"Exception saat mengambil riwayat percakapan untuk user {user_id}, session {session_id}: {e}", exc_info=True)
        return history

# --- Fungsi BARU untuk User Preferences ---
async def get_user_language_preference(user_id: int) -> Optional[str]:
    """Mengambil preferensi bahasa pengguna dari Supabase."""
    if not is_supabase_enabled():
        return None
    try:
        response = supabase_client.table("user_preferences").select("preferred_language_code").eq("user_id", user_id).maybe_single().execute()
        if response and not _is_supabase_response_error("mengambil preferensi bahasa", user_id, response):
            if isinstance(response.data, dict) and response.data.get("preferred_language_code"):
                return response.data["preferred_language_code"]
        return None # Tidak ada preferensi atau error
    except Exception as e:
        logging.error(f"Exception saat mengambil preferensi bahasa user {user_id}: {e}", exc_info=True)
        return None

async def set_user_language_preference(user_id: int, lang_code: str):
    """Menyimpan atau memperbarui preferensi bahasa pengguna di Supabase."""
    if not is_supabase_enabled():
        return
    try:
        response = supabase_client.table("user_preferences").upsert({
            "user_id": user_id,
            "preferred_language_code": lang_code,
            "updated_at": "now()"
        }).execute()
        if not _is_supabase_response_error("menyimpan preferensi bahasa", user_id, response):
            logging.info(f"Preferensi bahasa user {user_id} diatur ke {lang_code} di DB.")
    except Exception as e:
        logging.error(f"Exception saat menyimpan preferensi bahasa user {user_id}: {e}", exc_info=True)

async def get_user_model_preference(user_id: int) -> Optional[str]:
    """Mengambil preferensi model AI pengguna dari Supabase."""
    if not is_supabase_enabled():
        return None
    try:
        response = supabase_client.table("user_preferences").select("preferred_model_id").eq("user_id", user_id).maybe_single().execute()
        if response and not _is_supabase_response_error("mengambil preferensi model", user_id, response):
            if isinstance(response.data, dict) and response.data.get("preferred_model_id"):
                return response.data["preferred_model_id"]
        return None
    except Exception as e:
        logging.error(f"Exception saat mengambil preferensi model user {user_id}: {e}", exc_info=True)
        return None

async def set_user_model_preference(user_id: int, model_id: str):
    """Menyimpan atau memperbarui preferensi model AI pengguna di Supabase."""
    if not is_supabase_enabled():
        return
    try:
        response = supabase_client.table("user_preferences").upsert({
            "user_id": user_id,
            "preferred_model_id": model_id,
            "updated_at": "now()"
        }).execute()
        if not _is_supabase_response_error("menyimpan preferensi model", user_id, response):
            logging.info(f"Preferensi model user {user_id} diatur ke {model_id} di DB.")
    except Exception as e:
        logging.error(f"Exception saat menyimpan preferensi model user {user_id}: {e}", exc_info=True)
