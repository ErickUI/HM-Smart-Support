
import openai


class ServicioIAError(Exception):
    """Error con un mensaje ya listo para el usuario final."""

_PLANTILLAS = {
    openai.AuthenticationError: "La API Key de {servicio} no es válida o no está configurada. Revisa tu .env.",
    openai.PermissionDeniedError: "No tienes permiso para usar {servicio}{detalle}. Revisa tu cuenta o tu API Key.",
    openai.RateLimitError: "Se alcanzó el límite de uso de {servicio}{detalle}. Espera unos segundos o define un modelo de respaldo.",
    openai.NotFoundError: "El modelo{detalle} no está disponible en este proveedor. Revisa el ID en tu .env.",
    openai.BadRequestError: "La solicitud fue rechazada{detalle}. Verifica el modelo y el formato del archivo.",
    openai.APIConnectionError: "No se pudo conectar con {servicio}. Revisa tu conexión y la URL base configurada.",
}


def traducir_error(exc: Exception, servicio: str = "el servicio de IA", modelo: str = "") -> ServicioIAError:
    detalle = f" ({modelo})" if modelo else ""
    for tipo, plantilla in _PLANTILLAS.items():
        if isinstance(exc, tipo):
            return ServicioIAError(plantilla.format(servicio=servicio, detalle=detalle))
    if isinstance(exc, openai.APIStatusError):
        return ServicioIAError(f"{servicio} devolvió un error ({exc.status_code}). Intenta de nuevo en unos minutos.")
    return ServicioIAError(f"Ocurrió un error inesperado con {servicio}: {exc}")
