
import time
from dataclasses import dataclass

import openai
from openai import OpenAI

import config
from prompts.system_prompt import build_system_prompt
from services.errors import ServicioIAError, traducir_error


@dataclass
class RespuestaIA:
    texto: str
    modelo: str
    segundos: float


REINTENTABLES = (
    openai.RateLimitError,
    openai.NotFoundError,
    openai.BadRequestError,
    openai.InternalServerError,
    openai.APIConnectionError,
)

_cliente = None


def _obtener_cliente() -> OpenAI:
    global _cliente
    if not config.OPENAI_API_KEY:
        raise ServicioIAError("Falta OPENAI_API_KEY. Copia .env.example a .env y complétalo.")
    if _cliente is None:
        _cliente = OpenAI(api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL, timeout=60.0, max_retries=0)
    return _cliente


def completar(messages: list, temperature: float = None) -> RespuestaIA:
    """Envía los mensajes al modelo principal; si falla, prueba los modelos de respaldo."""
    cliente = _obtener_cliente()
    temp = config.TEMPERATURE if temperature is None else temperature
    modelos = [config.OPENAI_MODEL, *[m for m in config.OPENAI_FALLBACK_MODELS if m != config.OPENAI_MODEL]]
    error = None

    for modelo in modelos:
        for intento in range(2):
            inicio = time.perf_counter()
            try:
                r = cliente.chat.completions.create(model=modelo, messages=messages, temperature=temp)
            except REINTENTABLES as exc:
                error = traducir_error(exc, modelo=modelo)
                if isinstance(exc, openai.RateLimitError) and intento == 0:
                    time.sleep(2)
                    continue
                break
            except openai.OpenAIError as exc:
                raise traducir_error(exc, modelo=modelo) from exc

            texto = (r.choices[0].message.content or "").strip() if r.choices and r.choices[0].message else ""
            if texto:
                return RespuestaIA(texto, modelo, time.perf_counter() - inicio)
            error = ServicioIAError(f"{modelo} devolvió una respuesta vacía.")
            break

    raise error or ServicioIAError("No se pudo obtener respuesta del modelo.")


def responder(historial: list, version: str = None) -> RespuestaIA:
    """historial: lista de {"role", "content"} sin el prompt del sistema."""
    recientes = historial[-config.MAX_HISTORY_MESSAGES:]
    messages = [{"role": "system", "content": build_system_prompt(version or config.PROMPT_VERSION)}]
    messages += [{"role": m["role"], "content": m["content"]} for m in recientes]
    return completar(messages)
