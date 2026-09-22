"""Variables de entorno del proyecto. No se escriben claves aquí: todo viene del .env."""
import os

from dotenv import load_dotenv

load_dotenv()


def _lista(valor: str) -> list:
    return [v.strip() for v in valor.split(",") if v.strip()]


# Chat y clasificación: cualquier API compatible con OpenAI (OpenRouter, OpenAI, Gemini...)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openrouter/free").strip()
OPENAI_FALLBACK_MODELS = _lista(os.getenv("OPENAI_FALLBACK_MODELS", ""))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))
PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v3").strip().lower()

# Audio: transcripción con Whisper o un proveedor compatible
AUDIO_BASE_URL = os.getenv("AUDIO_BASE_URL", "https://api.openai.com/v1").strip()
OPENAI_AUDIO_MODEL = os.getenv("OPENAI_AUDIO_MODEL", "whisper-1").strip()
AUDIO_LANGUAGE = os.getenv("AUDIO_LANGUAGE", "es").strip()

_audio_key = os.getenv("AUDIO_API_KEY", "").strip()
if not _audio_key and "api.openai.com" in OPENAI_BASE_URL:
    _audio_key = OPENAI_API_KEY  # mismo proveedor para chat y audio: reutiliza la clave
AUDIO_API_KEY = _audio_key

AUDIO_EXTENSIONES = ("mp3", "wav", "m4a")
AUDIO_MAX_MB = 25
