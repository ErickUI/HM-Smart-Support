
import json
import re
import unicodedata

from prompts.system_prompt import CLASSIFIER_PROMPT
from services import chat_service
from services.errors import ServicioIAError

CATEGORIAS = ["informacion", "configuracion", "mantenimiento", "garantia", "repuesto", "falla", "servicio_tecnico", "otros"]
PRIORIDADES = ["baja", "media", "alta", "critica"]

ETIQUETAS = {
    "informacion": "Información",
    "configuracion": "Configuración",
    "mantenimiento": "Mantenimiento",
    "garantia": "Garantía",
    "repuesto": "Repuesto",
    "falla": "Falla",
    "servicio_tecnico": "Servicio técnico",
    "otros": "Otros",
}

# Estas palabras siempre elevan la prioridad a crítica, aunque el modelo se equivoque o falle.
_PATRON_CRITICO = re.compile(r"humo|quemad|chispa|cortocircuito|descarga electrica|incendio|fuego|explot")

_POR_DEFECTO = {
    "categoria": "otros",
    "prioridad": "media",
    "equipo": "no especificado",
    "problema": "ninguno",
    "requiere_atencion_tecnica": False,
    "recomendacion": "Revisar la consulta manualmente.",
}


def _normalizar(texto: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", str(texto).lower()) if unicodedata.category(c) != "Mn")
    return sin_tildes.strip()


def _extraer_json(texto: str) -> dict:
    limpio = re.sub(r"```(?:json)?", "", texto).strip()
    m = re.search(r"\{.*\}", limpio, re.DOTALL)
    if not m:
        raise ValueError("La respuesta del clasificador no contiene JSON.")
    return json.loads(m.group(0))


def _a_bool(valor) -> bool:
    if isinstance(valor, bool):
        return valor
    return _normalizar(valor) in ("true", "si", "sí", "1", "yes")


def _validar(datos: dict) -> dict:
    resultado = dict(_POR_DEFECTO)
    categoria = _normalizar(datos.get("categoria", "")).replace(" ", "_")
    prioridad = _normalizar(datos.get("prioridad", ""))
    resultado["categoria"] = categoria if categoria in CATEGORIAS else "otros"
    resultado["prioridad"] = prioridad if prioridad in PRIORIDADES else "media"
    resultado["equipo"] = str(datos.get("equipo") or "no especificado")
    resultado["problema"] = str(datos.get("problema") or "ninguno")
    resultado["requiere_atencion_tecnica"] = _a_bool(datos.get("requiere_atencion_tecnica", False))
    resultado["recomendacion"] = str(datos.get("recomendacion") or _POR_DEFECTO["recomendacion"])
    return resultado


def _aplicar_regla_critica(datos: dict, texto: str) -> dict:
    if _PATRON_CRITICO.search(_normalizar(texto)) and datos["prioridad"] != "critica":
        datos["prioridad"] = "critica"
        datos["requiere_atencion_tecnica"] = True
        if datos["categoria"] in ("otros", "informacion"):
            datos["categoria"] = "falla"
        datos["recomendacion"] = "Detener el uso del equipo, desconectarlo si es seguro y solicitar evaluación técnica."
        datos["fuente"] = datos.get("fuente", "reglas") + "+regla_critica"
    return datos


def clasificar_consulta(texto: str, contexto: str = "") -> dict:
    """Nunca lanza error: si la IA falla, usa reglas básicas y lo indica en el campo 'error'."""
    partes = []
    if contexto:
        partes.append(f"<contexto>\n{contexto}\n</contexto>")
    partes.append(f"<consulta>{texto}</consulta>")
    mensajes = [
        {"role": "system", "content": CLASSIFIER_PROMPT},
        {"role": "user", "content": "\n".join(partes)},
    ]
    try:
        r = chat_service.completar(mensajes, temperature=0)
        datos = _validar(_extraer_json(r.texto))
        datos["fuente"] = "modelo"
        datos["segundos"] = round(r.segundos, 2)
    except (ServicioIAError, ValueError) as exc:
        datos = dict(_POR_DEFECTO)
        datos["fuente"] = "reglas"
        datos["error"] = str(exc)
    return _aplicar_regla_critica(datos, texto)
