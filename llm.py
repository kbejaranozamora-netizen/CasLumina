"""Capa de IA: Gemini (SDK google-genai) con herramientas (function calling).

TODO lo que sabe de Gemini vive aquí. El resto de la app solo llama a conversar() y atrapa ErrorLLM.
Si algún día cambia el modelo o el proveedor, se toca este archivo y nada más.

Reglas de esta capa:
 - Cada llamada a la API va dentro de try/except y se traduce a un mensaje claro para el usuario.
 - El usuario NUNCA ve el error crudo (puede traer detalles técnicos); el detalle va solo al log.
 - La clave nunca se imprime: si aparece en un mensaje de error, se tapa.
"""
from __future__ import annotations

import logging

log = logging.getLogger("casa_lumina.llm")

_CLAVE = ""  # solo para taparla en mensajes de error; nunca se escribe en ningún lado

MENSAJES = {
    "cuota": (
        "El asistente de IA gratuito llegó a su límite por ahora. Puedes seguir con el Tablero, que no usa IA, "
        "o volver a intentar en unos minutos (si el límite es el diario, se renueva mañana)."
    ),
    "conexion": (
        "No pude conectarme con el servicio de IA. Revisa tu conexión a internet e intenta de nuevo. "
        "Mientras tanto, el Tablero sigue disponible."
    ),
    "clave": (
        "La clave del servicio de IA falta o no es válida. Esto lo tiene que revisar quien administra la app. "
        "El Tablero sigue disponible."
    ),
    "saturado": "El servicio de IA está saturado en este momento. Intenta de nuevo en un minuto.",
    "modelo": "El modelo de IA configurado no está disponible. Esto lo tiene que revisar quien administra la app.",
    "vacia": "El asistente no devolvió una respuesta. Intenta reformular la pregunta.",
    "otro": "Algo salió mal al consultar. Intenta reformular la pregunta o vuelve a intentarlo en un momento.",
}

TEXTO_SIN_CIERRE = "No logré cerrar la consulta en los pasos permitidos. Reformula la pregunta con algo más específico."


class ErrorLLM(Exception):
    """Error de la capa de IA ya traducido: .tipo identifica el caso y .mensaje es apto para el usuario."""

    def __init__(self, tipo: str, detalle: str = ""):
        self.tipo = tipo if tipo in MENSAJES else "otro"
        self.mensaje = MENSAJES[self.tipo]
        self.detalle = detalle
        super().__init__(self.mensaje)


def _tapar(texto: str) -> str:
    texto = str(texto)
    return texto.replace(_CLAVE, "***") if _CLAVE else texto


def clasificar_error(exc: BaseException) -> ErrorLLM:
    """Traduce cualquier excepción del SDK, de red o de código a un ErrorLLM con mensaje claro."""
    if isinstance(exc, ErrorLLM):
        return exc
    codigo = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    try:
        codigo = int(codigo) if codigo is not None else None
    except (TypeError, ValueError):
        codigo = None
    estado = str(getattr(exc, "status", "") or "").upper()
    nombre = type(exc).__name__.lower()
    msg = _tapar(exc).lower()

    if codigo == 429 or "RESOURCE_EXHAUSTED" in estado or "resource_exhausted" in msg or "quota" in msg or "rate limit" in msg:
        tipo = "cuota"
    elif codigo in (401, 403) or "UNAUTHENTICATED" in estado or "PERMISSION_DENIED" in estado or "api key" in msg:
        tipo = "clave"
    elif codigo == 404 or "NOT_FOUND" in estado:
        tipo = "modelo"
    elif codigo in (500, 502, 503, 504) or "UNAVAILABLE" in estado or "overloaded" in msg:
        tipo = "saturado"
    elif (
        isinstance(exc, (ConnectionError, TimeoutError))
        or any(k in nombre for k in ("connect", "timeout", "network", "dns"))
        or any(k in msg for k in ("connection", "name or service not known", "timed out", "network is unreachable"))
    ):
        tipo = "conexion"
    else:
        tipo = "otro"
    return ErrorLLM(tipo, detalle=f"{type(exc).__name__}: {_tapar(exc)}")


def crear_cliente(api_key: str):
    """Crea el cliente de Gemini. La clave llega de los secretos de la plataforma, nunca del código."""
    global _CLAVE
    from google import genai

    _CLAVE = api_key
    return genai.Client(api_key=api_key)


def _a_schema(js: dict, types):
    """Convierte un esquema JSON simple (el de TOOLS) al formato de Gemini."""
    tipo = str(js.get("type", "string")).upper()
    kw = {"type": getattr(types.Type, tipo)}
    if "description" in js:
        kw["description"] = js["description"]
    if "enum" in js:
        kw["enum"] = list(js["enum"])
    if tipo == "OBJECT":
        kw["properties"] = {k: _a_schema(v, types) for k, v in js.get("properties", {}).items()}
        if js.get("required"):
            kw["required"] = list(js["required"])
    if tipo == "ARRAY":
        kw["items"] = _a_schema(js.get("items", {"type": "string"}), types)
    return types.Schema(**kw)


def declaraciones(tools: list[dict], types):
    """TOOLS (nombre, descripción, input_schema) -> herramienta de Gemini."""
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name=t["name"], description=t["description"], parameters=_a_schema(t["input_schema"], types)
            )
            for t in tools
        ]
    )


def _a_contents(historial: list[dict], pregunta: str, types) -> list:
    """Historial (solo texto) + la pregunta nueva -> contenidos de Gemini. 'assistant' se llama 'model'."""
    contenidos = [
        types.Content(role="user" if m["role"] == "user" else "model", parts=[types.Part(text=m["content"])])
        for m in historial
    ]
    contenidos.append(types.Content(role="user", parts=[types.Part(text=pregunta)]))
    return contenidos


def _texto(resp) -> str:
    try:
        return (resp.text or "").strip()
    except Exception:  # respuesta sin texto (bloqueada, vacía...)
        return ""


def conversar(client, *, system: str, historial: list[dict], pregunta: str, tools: list[dict],
              despachar, modelos: list[str], max_pasos: int = 6) -> str:
    """Corre el ciclo pregunta -> herramientas -> respuesta. Devuelve el texto final.

    despachar(nombre, args) -> str  ejecuta la herramienta y devuelve lo que el modelo verá.
    modelos: [principal, respaldo]. Si el principal responde «cuota agotada», se prueba el respaldo.
    Lanza ErrorLLM con mensaje claro si algo falla.
    """
    from google.genai import types

    modelos = [m for m in modelos if m]
    config = types.GenerateContentConfig(system_instruction=system, tools=[declaraciones(tools, types)])
    contenidos = _a_contents(historial, pregunta, types)
    i = 0  # índice del modelo en uso

    for _ in range(max_pasos):
        resp = None
        while resp is None:
            try:
                resp = client.models.generate_content(model=modelos[i], contents=contenidos, config=config)
            except Exception as e:  # cuota agotada, clave incorrecta, red caída...
                err = clasificar_error(e)
                log.warning("Fallo de IA (%s) con %s: %s", err.tipo, modelos[i], err.detalle)
                if err.tipo in ("cuota", "saturado", "modelo") and i + 1 < len(modelos):
                    i += 1  # prueba el modelo de respaldo
                    continue
                raise err from e

        llamadas = list(getattr(resp, "function_calls", None) or [])
        if not llamadas:
            texto = _texto(resp)
            if not texto:
                raise ErrorLLM("vacia")
            return texto

        # el modelo pidió herramientas: se guarda su turno tal cual (trae sus firmas de razonamiento) y se responde
        candidato = (getattr(resp, "candidates", None) or [None])[0]
        contenidos.append(candidato.content)
        partes = []
        for fc in llamadas:
            salida = despachar(fc.name, dict(fc.args or {}))
            partes.append(types.Part.from_function_response(name=fc.name, response={"result": salida}))
        contenidos.append(types.Content(role="user", parts=partes))

    return TEXTO_SIN_CIERRE
