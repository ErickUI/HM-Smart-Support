"""Ejecuta los casos de prueba y guarda la matriz en evidence/matriz_pruebas_<version>.csv.

  python tests/run_tests.py                  # ejecuta con el prompt V3
  python tests/run_tests.py --prompt v1      # ejecuta con otra versión
  python tests/run_tests.py --metricas       # calcula métricas desde el CSV ya revisado

Para los casos de audio, coloca en tests/audio/: prueba.wav, prueba.mp3 y prueba.m4a
Los casos de texto quedan con "Cumple" vacío hasta que los revises y marques Sí/No;
los de clasificación (CP11, CP12) se marcan solos.
"""
import argparse
import csv
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from services import audio_service, chat_service, classifier_service  # noqa: E402
from services.errors import ServicioIAError  # noqa: E402

AUDIO_DIR = RAIZ / "tests" / "audio"
EVIDENCE_DIR = RAIZ / "evidence"
COLUMNAS = ["ID", "Escenario", "Entrada", "Esperado", "Obtenido", "Cumple",
            "Clasificacion_correcta", "Tiempo_s", "Observaciones"]

CASOS = [
    {"id": "CP01", "escenario": "Consulta simple", "turnos": ["¿Qué tipos de máquinas venden y qué servicios de postventa ofrecen?"],
     "esperado": "Respuesta pertinente al dominio"},
    {"id": "CP02", "escenario": "Consulta de mantenimiento", "turnos": ["¿Qué mantenimiento necesita una remalladora?"],
     "esperado": "Orientación clara", "clasif": ("mantenimiento", ("baja", "media"))},
    {"id": "CP03", "escenario": "Consulta de configuración", "turnos": ["¿Cómo enhebro correctamente mi máquina recta?"],
     "esperado": "Pasos comprensibles", "clasif": ("configuracion", ("baja", "media"))},
    {"id": "CP04", "escenario": "Pregunta ambigua", "turnos": ["Mi máquina no funciona bien, ¿qué hago?"],
     "esperado": "Solicita aclaración"},
    {"id": "CP05", "escenario": "Información desconocida", "turnos": ["¿Cuál es el precio exacto del repuesto del modelo ZX-4000 y hay stock hoy?"],
     "esperado": "No inventa información"},
    {"id": "CP06", "escenario": "Tema fuera del dominio", "turnos": ["Dame una receta de ceviche."],
     "esperado": "Redirige correctamente", "clasif": ("otros", ("baja",))},
    {"id": "CP07", "escenario": "Conversación con seguimiento",
     "turnos": ["¿Qué mantenimiento necesita una remalladora?", "¿Y cada cuánto tiempo debo hacerlo?"],
     "esperado": "Mantiene contexto"},
    {"id": "CP08", "escenario": "Audio WAV", "audio": ["wav"], "esperado": "Transcribe correctamente"},
    {"id": "CP09", "escenario": "Audio MP3/M4A", "audio": ["mp3", "m4a"], "esperado": "Transcribe correctamente"},
    {"id": "CP10", "escenario": "Audio → chatbot", "audio": ["wav", "mp3", "m4a"], "responder": True,
     "esperado": "Transcribe y responde"},
    {"id": "CP11", "escenario": "Falla técnica", "turnos": ["Mi bordadora hace un ruido fuerte y la aguja se traba."],
     "esperado": "Clasifica categoría/prioridad", "clasif": ("falla", ("alta",)), "auto": True},
    {"id": "CP12", "escenario": "Situación crítica", "turnos": ["Mi remalladora comenzó a botar humo y tiene olor a quemado."],
     "esperado": "Asigna prioridad adecuada", "clasif": ("falla", ("critica",)), "auto": True},
]


def _clasificacion_correcta(clasif: dict, esperado: tuple) -> bool:
    categoria, prioridades = esperado
    return clasif["categoria"] == categoria and clasif["prioridad"] in prioridades


def _buscar_audio(extensiones):
    for ext in extensiones:
        ruta = AUDIO_DIR / f"prueba.{ext}"
        if ruta.exists():
            return ruta
    return None


def ejecutar_caso(caso: dict, version: str) -> dict:
    fila = {c: "" for c in COLUMNAS}
    fila.update({"ID": caso["id"], "Escenario": caso["escenario"], "Esperado": caso["esperado"]})
    try:
        if "audio" in caso:
            fila.update(_ejecutar_audio(caso, version))
        else:
            fila.update(_ejecutar_texto(caso, version))
    except ServicioIAError as exc:
        fila["Obtenido"] = f"ERROR: {exc}"
        fila["Cumple"] = "No"
        fila["Observaciones"] = "Falló el servicio o la configuración"
    return fila


def _ejecutar_texto(caso: dict, version: str) -> dict:
    historial, ultima = [], None
    for turno in caso["turnos"]:
        historial.append({"role": "user", "content": turno})
        ultima = chat_service.responder(historial, version=version)
        historial.append({"role": "assistant", "content": ultima.texto})
    salida = {"Entrada": " || ".join(caso["turnos"]), "Obtenido": ultima.texto, "Tiempo_s": f"{ultima.segundos:.2f}"}

    if "clasif" in caso:
        clasif = classifier_service.clasificar_consulta(caso["turnos"][-1])
        correcta = _clasificacion_correcta(clasif, caso["clasif"])
        salida["Clasificacion_correcta"] = "Sí" if correcta else "No"
        salida["Obtenido"] += f"\n[Clasificación: {clasif['categoria']} / {clasif['prioridad']}]"
        if caso.get("auto"):
            salida["Cumple"] = salida["Clasificacion_correcta"]
    return salida


def _ejecutar_audio(caso: dict, version: str) -> dict:
    if caso["id"] == "CP09":
        rutas = [AUDIO_DIR / "prueba.mp3", AUDIO_DIR / "prueba.m4a"]
    else:
        ruta = _buscar_audio(caso["audio"])
        rutas = [ruta] if ruta else []
    faltantes = [r for r in rutas if not r.exists()] or ([] if rutas else [AUDIO_DIR / "prueba.*"])
    if faltantes:
        return {"Obtenido": "PENDIENTE: faltan " + ", ".join(f.name for f in faltantes) + " en tests/audio/",
                "Observaciones": "Agrega los audios de prueba y vuelve a ejecutar"}

    transcripciones, texto_final, inicio = [], "", time.perf_counter()
    for ruta in rutas:
        texto = audio_service.transcribir_bytes(ruta.name, ruta.read_bytes())
        transcripciones.append(f"{ruta.name}: {texto}")
        texto_final = texto
    salida = {"Entrada": ", ".join(r.name for r in rutas), "Obtenido": "\n".join(transcripciones)}
    if caso.get("responder"):
        r = chat_service.responder([{"role": "user", "content": texto_final}], version=version)
        salida["Obtenido"] += f"\n[Respuesta del chatbot] {r.texto}"
        salida["Tiempo_s"] = f"{time.perf_counter() - inicio:.2f}"
    return salida


def ejecutar(version: str):
    EVIDENCE_DIR.mkdir(exist_ok=True)
    destino = EVIDENCE_DIR / f"matriz_pruebas_{version}.csv"
    filas = []
    for caso in CASOS:
        print(f"Ejecutando {caso['id']} - {caso['escenario']}...")
        filas.append(ejecutar_caso(caso, version))
        time.sleep(1.5)  # margen para no chocar con límites de planes gratuitos
    with open(destino, "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(filas)
    print(f"\nMatriz guardada en {destino}")
    print("Revisa la columna 'Cumple' (Sí/No) y luego ejecuta: python tests/run_tests.py --metricas")


def metricas(version: str):
    origen = EVIDENCE_DIR / f"matriz_pruebas_{version}.csv"
    if not origen.exists():
        sys.exit(f"No existe {origen}. Ejecuta primero las pruebas.")
    with open(origen, newline="", encoding="utf-8-sig") as f:
        filas = list(csv.DictReader(f))

    evaluadas = [f for f in filas if f["Cumple"] in ("Sí", "No")]
    pendientes = [f["ID"] for f in filas if f["Cumple"] not in ("Sí", "No")]
    ok = sum(1 for f in evaluadas if f["Cumple"] == "Sí")
    clasif = [f for f in filas if f["Clasificacion_correcta"] in ("Sí", "No")]
    clasif_ok = sum(1 for f in clasif if f["Clasificacion_correcta"] == "Sí")
    tiempos = []
    for f in filas:
        try:
            tiempos.append(float(f["Tiempo_s"]))
        except ValueError:
            pass

    print(f"Prompt evaluado: {version.upper()}")
    if pendientes:
        print(f"Aviso: casos sin calificar (Cumple vacío): {', '.join(pendientes)}")
    if evaluadas:
        print(f"Tasa de pruebas satisfactorias: {ok}/{len(evaluadas)} = {ok / len(evaluadas) * 100:.1f} %")
    if clasif:
        print(f"Exactitud de clasificación: {clasif_ok}/{len(clasif)} = {clasif_ok / len(clasif) * 100:.1f} %")
    if tiempos:
        print(f"Tiempo promedio de respuesta: {sum(tiempos) / len(tiempos):.2f} s ({len(tiempos)} consultas)")
        if len(tiempos) < 10:
            print("Sugerencia: registra al menos 10 consultas para que el promedio sea representativo.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pruebas funcionales de HM Smart Support")
    parser.add_argument("--prompt", default="v3", choices=["v1", "v2", "v3"], help="versión del prompt")
    parser.add_argument("--metricas", action="store_true", help="calcular métricas desde el CSV revisado")
    args = parser.parse_args()
    if args.metricas:
        metricas(args.prompt)
    else:
        ejecutar(args.prompt)
