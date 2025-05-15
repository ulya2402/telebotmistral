import logging
from mistralai import Mistral 
from config import MISTRAL_API_KEY 

mistral_client = None


if MISTRAL_API_KEY:
    try:
        mistral_client = Mistral(api_key=MISTRAL_API_KEY)
        
        logging.info("Klien Mistral (kelas Mistral) berhasil diinisialisasi.")
    except Exception as e:
        logging.error(f"Gagal menginisialisasi klien Mistral (kelas Mistral): {e}")
else:
    
    logging.error("MISTRAL_API_KEY tidak ditemukan. Tidak dapat menginisialisasi klien Mistral.")

def get_mistral_client():
    """Mengembalikan instance klien Mistral yang sudah diinisialisasi."""
    return mistral_client
