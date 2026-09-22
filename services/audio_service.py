
from pathlib import Path

import openai
from openai import OpenAI

import config
from services.errors import ServicioIAError, traducir_error


def _cliente() -> OpenAI:
    if not config.AUDIO_API_KEY:
        raise ServicioIAError("Falta AUDIO_API_KEY. Complétalo en tu archivo .env.")
    return OpenAI(api_key=config.AUDIO_API_KEY, base_url=config.AUDIO_BASE_URL, timeout=120.0, max_retries=1)


def validar_audio(nombre: str, tamano_bytes: int) -> None:
    extension = Path(nombre).suffix.lower().lstrip(".")
    if extension not in config.AUDIO_EXTENSIONES:
        permitidos = ", ".join(e.upper() for e in config.AUDIO_EXTENSIONES)
        raise ServicioIAError(f"Formato no permitido (.{extension}). Usa un archivo {permitidos}.")
    if tamano_bytes == 0:
        raise ServicioIAError("El archivo de audio está vacío.")
    if tamano_bytes > config.AUDIO_MAX_MB * 1024 * 1024:
        raise ServicioIAError(f"El audio supera el máximo de {config.AUDIO_MAX_MB} MB.")


def transcribir_bytes(nombre: str, datos: bytes) -> str:
    validar_audio(nombre, len(datos))
    try:
        resultado = _cliente().audio.transcriptions.create(
            model=config.OPENAI_AUDIO_MODEL,
            file=(nombre, datos),
            language=config.AUDIO_LANGUAGE,
        )
    except openai.OpenAIError as exc:
        raise traducir_error(exc, servicio="transcripción", modelo=config.OPENAI_AUDIO_MODEL) from exc

    texto = (resultado.text or "").strip()
    if not texto:
        raise ServicioIAError("No se detectó voz en el audio. Prueba con otra grabación.")
    return texto


def transcribir_audio(archivo) -> str:
    """archivo: objeto de st.file_uploader (expone .name y .getvalue())."""
    return transcribir_bytes(archivo.name, archivo.getvalue())
