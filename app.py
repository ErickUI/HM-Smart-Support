
from pathlib import Path

import streamlit as st

import config
from services import audio_service, chat_service, classifier_service
from services.errors import ServicioIAError

RAIZ = Path(__file__).resolve().parent
CLAVE_TRANSCRIPCION = "transcripcion_editable"
CLASE_BADGE = {"baja": "hm-badge-baja", "media": "hm-badge-media", "alta": "hm-badge-alta", "critica": "hm-badge-critica"}

st.set_page_config(page_title="HM Smart Support", page_icon="🧵", layout="wide")


def inyectar_estilos():
    css = (RAIZ / "assets" / "style.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def iniciar_estado():
    base = {
        "messages": [],
        "tiempos": [],
        "audio_cache": None,
        "ultima_audio": None,
        "uploader_n": 0,
        "version_prompt": config.PROMPT_VERSION if config.PROMPT_VERSION in ("v1", "v2", "v3") else "v3",
    }
    for clave, valor in base.items():
        st.session_state.setdefault(clave, valor)


def reiniciar_sesion():
    for clave in ("messages", "tiempos", "audio_cache", "ultima_audio", CLAVE_TRANSCRIPCION):
        st.session_state.pop(clave, None)
    st.session_state["uploader_n"] = int(st.session_state.get("uploader_n", 0)) + 1


def contexto_reciente(max_mensajes: int = 4) -> str:
    previos = st.session_state.messages[:-1][-max_mensajes:]
    return "\n".join(f"{m['role']}: {m['content'][:300]}" for m in previos)


def procesar_consulta(texto: str, origen: str = "texto") -> dict:
    st.session_state.messages.append({"role": "user", "content": texto, "origen": origen})
    historial = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
    try:
        respuesta = chat_service.responder(historial, version=st.session_state.version_prompt)
    except ServicioIAError:
        st.session_state.messages.pop()
        raise

    clasificacion = classifier_service.clasificar_consulta(texto, contexto_reciente())
    mensaje = {
        "role": "assistant",
        "content": respuesta.texto,
        "clasificacion": clasificacion,
        "modelo": respuesta.modelo,
        "segundos": respuesta.segundos,
    }
    st.session_state.messages.append(mensaje)
    st.session_state.tiempos.append(respuesta.segundos)
    return mensaje


def badge_prioridad(prioridad: str) -> str:
    clase = CLASE_BADGE.get(prioridad, "hm-badge-media")
    return f'<span class="hm-badge {clase}">{prioridad.capitalize()}</span>'


def panel_clasificacion(msg: dict):
    c = msg["clasificacion"]
    categoria = classifier_service.ETIQUETAS.get(c["categoria"], c["categoria"])
    atencion = "Sí" if c["requiere_atencion_tecnica"] else "No"
    st.markdown(
        f"""<div class="hm-card">
        <div class="hm-card-row"><span>Categoría</span><strong>{categoria}</strong></div>
        <div class="hm-card-row"><span>Prioridad</span>{badge_prioridad(c['prioridad'])}</div>
        <div class="hm-card-row"><span>Atención técnica</span><strong>{atencion}</strong></div>
        </div>""",
        unsafe_allow_html=True,
    )
    if c.get("recomendacion"):
        st.caption(c["recomendacion"])
    if c.get("error"):
        st.caption("La clasificación automática falló; se aplicó una regla de respaldo.")
    with st.expander("Ver salida estructurada"):
        st.json({k: v for k, v in c.items() if k not in ("error", "segundos")})
    st.caption(f"{msg['segundos']:.1f} s · {msg['modelo']}")


def mostrar_mensaje(msg: dict):
    avatar = "🧵" if msg["role"] == "assistant" else None
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])
        if msg["role"] == "user" and msg.get("origen") == "audio":
            st.caption("Consulta transcrita desde un audio")
        if msg["role"] == "assistant" and "clasificacion" in msg:
            panel_clasificacion(msg)


def encabezado():
    st.markdown(
        """<div class="hm-hero">
          <div>
            <span class="hm-hero-tag">Hilos y Máquinas · Postventa</span>
            <h1 class="hm-hero-brand">HM Smart Support</h1>
          </div>
          <div class="hm-status-chip"><span class="hm-status-dot"></span>Atendiendo consultas</div>
        </div>
        <div class="hm-stitch"></div>""",
        unsafe_allow_html=True,
    )


def barra_metricas():
    consultas = sum(1 for m in st.session_state.messages if m["role"] == "user")
    tiempos = st.session_state.tiempos
    promedio = sum(tiempos) / len(tiempos) if tiempos else 0
    st.markdown(
        f"""<div class="hm-ticket">
          <div class="hm-ticket-item"><span class="hm-ticket-value">{consultas}</span>
            <span class="hm-ticket-label">Consultas en la sesión</span></div>
          <div class="hm-ticket-item"><span class="hm-ticket-value">{promedio:.1f}s</span>
            <span class="hm-ticket-label">Tiempo promedio de respuesta</span></div>
          <div class="hm-ticket-item"><span class="hm-ticket-value">{st.session_state.version_prompt.upper()}</span>
            <span class="hm-ticket-label">Prompt activo</span></div>
        </div>""",
        unsafe_allow_html=True,
    )


def barra_lateral():
    with st.sidebar:
        st.markdown("### Panel de control")
        st.selectbox("Versión del prompt", ["v1", "v2", "v3"], key="version_prompt", format_func=str.upper)
        st.button("Reiniciar conversación", on_click=reiniciar_sesion, use_container_width=True)
        st.divider()
        if not config.OPENAI_API_KEY:
            st.error("Falta OPENAI_API_KEY en tu .env: el chat no responderá.")
        if not config.AUDIO_API_KEY:
            st.warning("Falta AUDIO_API_KEY en tu .env: el audio no se transcribirá.")
        st.caption(f"Chat: {config.OPENAI_MODEL}")
        st.caption(f"Audio: {config.OPENAI_AUDIO_MODEL}")


def seccion_chat():
    if not st.session_state.messages:
        st.markdown(
            '<div class="hm-card hm-welcome">Cuéntanos qué le pasa a tu máquina — configuración, '
            "mantenimiento, una falla o una consulta de garantía — y te ayudamos a resolverlo.</div>",
            unsafe_allow_html=True,
        )
    for m in st.session_state.messages:
        mostrar_mensaje(m)

    consulta = st.chat_input("Escribe tu consulta...")
    if consulta:
        with st.chat_message("user"):
            st.markdown(consulta)
        with st.chat_message("assistant", avatar="🧵"):
            with st.spinner("Revisando tu consulta..."):
                try:
                    respuesta = procesar_consulta(consulta)
                except ServicioIAError as exc:
                    st.error(str(exc))
                else:
                    st.markdown(respuesta["content"])
                    panel_clasificacion(respuesta)


def seccion_audio():
    st.caption("Formatos admitidos: MP3, WAV y M4A · máximo 25 MB")
    archivo = st.file_uploader(
        "Sube la nota de voz del cliente",
        type=list(config.AUDIO_EXTENSIONES),
        key=f"audio_{st.session_state.uploader_n}",
    )

    if archivo is None:
        st.session_state.audio_cache = None
        st.session_state.ultima_audio = None
        return

    st.write(f"{archivo.name} · {archivo.size / 1024:.0f} KB")
    st.audio(archivo.getvalue())

    clave_archivo = f"{archivo.name}-{archivo.size}"
    cache = st.session_state.audio_cache
    if not cache or cache["clave"] != clave_archivo:
        st.session_state.ultima_audio = None
        with st.spinner("Transcribiendo..."):
            try:
                texto = audio_service.transcribir_audio(archivo)
                cache = {"clave": clave_archivo, "texto": texto, "error": None}
                st.session_state[CLAVE_TRANSCRIPCION] = texto
            except ServicioIAError as exc:
                cache = {"clave": clave_archivo, "texto": "", "error": str(exc)}
        st.session_state.audio_cache = cache

    if cache["error"]:
        st.error(cache["error"])
        if st.button("Reintentar transcripción"):
            st.session_state.audio_cache = None
            st.rerun()
        return

    if CLAVE_TRANSCRIPCION not in st.session_state:
        st.session_state[CLAVE_TRANSCRIPCION] = cache["texto"]
    st.text_area("Transcripción (puedes corregirla antes de enviarla)", key=CLAVE_TRANSCRIPCION, height=140)

    if st.button("Usar como consulta", type="primary"):
        texto_consulta = st.session_state[CLAVE_TRANSCRIPCION].strip()
        if not texto_consulta:
            st.warning("La transcripción está vacía.")
        else:
            with st.spinner("Consultando..."):
                try:
                    st.session_state.ultima_audio = procesar_consulta(texto_consulta, origen="audio")
                except ServicioIAError as exc:
                    st.error(str(exc))
                else:
                    st.rerun()

    if st.session_state.ultima_audio:
        st.divider()
        st.markdown("**Respuesta del chatbot**")
        st.markdown(st.session_state.ultima_audio["content"])
        panel_clasificacion(st.session_state.ultima_audio)


inyectar_estilos()
iniciar_estado()
barra_lateral()
encabezado()
barra_metricas()

tab_chat, tab_audio = st.tabs(["Conversar", "Nota de voz"])
with tab_chat:
    seccion_chat()
with tab_audio:
    seccion_audio()
