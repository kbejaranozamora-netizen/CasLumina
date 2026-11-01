"""Autotest de la capa de IA (llm.py) SIN red, SIN clave y SIN el SDK real de Gemini.
Usa un Gemini simulado para comprobar: el ciclo de herramientas, el modelo de respaldo cuando se acaba la cuota,
y que cada falla (cuota, conexión, clave, saturación...) se convierta en un mensaje claro sin filtrar detalles ni la clave.
Uso: python selftest_llm.py
"""
import sys
import types as pytypes


# ------------------------------------------------------------- Gemini simulado (solo lo que usa llm.py)
class Registro:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class Type:
    STRING, NUMBER, INTEGER, BOOLEAN, ARRAY, OBJECT = "STRING", "NUMBER", "INTEGER", "BOOLEAN", "ARRAY", "OBJECT"


class Part(Registro):
    def __init__(self, text=None, function_response=None):
        super().__init__(text=text, function_response=function_response)

    @classmethod
    def from_function_response(cls, name, response):
        return cls(function_response={"name": name, "response": response})


tipos = pytypes.ModuleType("google.genai.types")
tipos.Type = Type
tipos.Schema = lambda **kw: Registro(**kw)
tipos.FunctionDeclaration = lambda **kw: Registro(**kw)
tipos.Tool = lambda **kw: Registro(**kw)
tipos.GenerateContentConfig = lambda **kw: Registro(**kw)
tipos.Part = Part
tipos.Content = lambda role, parts: Registro(role=role, parts=parts)

claves_creadas = []
genai = pytypes.ModuleType("google.genai")
genai.types = tipos
genai.Client = lambda api_key: claves_creadas.append(api_key) or Registro(api_key=api_key)
google = pytypes.ModuleType("google")
google.genai = genai
sys.modules.update({"google": google, "google.genai": genai, "google.genai.types": tipos})

import llm  # noqa: E402  (se importa después de instalar el Gemini simulado)

llm.ESPERA_REINTENTO = ()  # las pruebas no esperan de verdad; los reintentos se prueban aparte

try:  # si el motor de consultas está instalado, se usan las herramientas reales
    from agent import TOOLS
except Exception:
    TOOLS = [
        {"name": "run_sql", "description": "d", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
        {"name": "show_visual", "description": "d", "input_schema": {"type": "object", "properties": {
            "kind": {"type": "string", "enum": ["bar", "line"]}, "y": {"type": "array", "items": {"type": "string"}},
            "stacked": {"type": "boolean"}}, "required": ["kind"]}},
    ]


class Llamada(Registro):
    pass


class Respuesta:
    def __init__(self, texto=None, llamadas=None):
        self._texto = texto
        self.function_calls = llamadas or []
        self.candidates = [Registro(content=Registro(role="model", parts=["(turno del modelo)"]))]

    @property
    def text(self):
        return self._texto


class ErrorApi(Exception):
    def __init__(self, code, status="", msg=""):
        super().__init__(msg or f"{code} {status}")
        self.code, self.status = code, status


class ClienteFalso:
    """Devuelve, en orden, las respuestas (o lanza las excepciones) que se le indiquen."""

    def __init__(self, guion):
        self.guion, self.llamadas = list(guion), []
        self.models = self

    def generate_content(self, model, contents, config):
        self.llamadas.append(Registro(model=model, contents=list(contents), config=config))
        paso = self.guion.pop(0)
        if isinstance(paso, Exception):
            raise paso
        return paso


ok = True


def check(nombre, cond, detalle=""):
    global ok
    ok = ok and cond
    print(("PASS  " if cond else "FAIL  ") + nombre + (f"  {detalle}" if detalle and not cond else ""))


def conversar(cliente, despachar=lambda n, a: "ok", historial=None, modelos=("principal", "respaldo"), max_pasos=6):
    return llm.conversar(cliente, system="SISTEMA", historial=historial or [], pregunta="¿cómo vamos?",
                         tools=TOOLS, despachar=despachar, modelos=list(modelos), max_pasos=max_pasos)


def falla(cliente, **kw):
    try:
        conversar(cliente, **kw)
    except llm.ErrorLLM as e:
        return e
    return None


# ------------------------------------------------------------- 1) herramientas -> formato Gemini
decl = llm.declaraciones(TOOLS, tipos)
check("convierte todas las herramientas", [d.name for d in decl.function_declarations] == [t["name"] for t in TOOLS])
vis = next(d for d in decl.function_declarations if d.name == "show_visual").parameters
check("el esquema conserva tipos, listas y enumeraciones",
      vis.type == Type.OBJECT and vis.properties["y"].type == Type.ARRAY and vis.properties["y"].items.type == Type.STRING
      and "bar" in vis.properties["kind"].enum and vis.properties["stacked"].type == Type.BOOLEAN)

# ------------------------------------------------------------- 2) respuesta directa
c = ClienteFalso([Respuesta(texto="Vamos bien.")])
r = conversar(c, historial=[{"role": "user", "content": "hola"}, {"role": "assistant", "content": "¡hola!"}])
check("devuelve el texto del modelo", r == "Vamos bien.")
cont = c.llamadas[0].contents
check("el historial traduce 'assistant' a 'model' y agrega la pregunta nueva",
      [x.role for x in cont] == ["user", "model", "user"] and cont[-1].parts[0].text == "¿cómo vamos?")
check("manda las instrucciones del sistema y las herramientas",
      c.llamadas[0].config.system_instruction == "SISTEMA" and len(c.llamadas[0].config.tools) == 1)
check("usa el modelo principal primero", c.llamadas[0].model == "principal")

# ------------------------------------------------------------- 3) ciclo de herramientas
vistos = []
c = ClienteFalso([
    Respuesta(llamadas=[Llamada(name="run_sql", args={"query": "SELECT 1"})]),
    Respuesta(texto="Resultado final."),
])
r = conversar(c, despachar=lambda n, a: vistos.append((n, a)) or "tabla: 1")
check("ejecuta la herramienta que pidió el modelo", vistos == [("run_sql", {"query": "SELECT 1"})])
check("le devuelve el resultado al modelo y obtiene la respuesta final", r == "Resultado final.")
ultimo = c.llamadas[1].contents[-1]
check("la respuesta de la herramienta va como turno de usuario con el resultado",
      ultimo.role == "user" and ultimo.parts[0].function_response == {"name": "run_sql", "response": {"result": "tabla: 1"}})
check("se conserva el turno del modelo con la petición de herramienta", c.llamadas[1].contents[-2].role == "model")

c = ClienteFalso([
    Respuesta(llamadas=[Llamada(name="run_sql", args={"query": "a"}), Llamada(name="show_visual", args={"kind": "bar"})]),
    Respuesta(texto="Listo."),
])
conversar(c)
check("varias herramientas en un turno se responden juntas", len(c.llamadas[1].contents[-1].parts) == 2)

c = ClienteFalso([Respuesta(llamadas=[Llamada(name="run_sql", args={"query": "x"})]) for _ in range(3)])
r = conversar(c, max_pasos=3)
check("si el modelo nunca termina, corta con un mensaje claro", r == llm.TEXTO_SIN_CIERRE and len(c.llamadas) == 3)

# en el último paso se quitan las herramientas para obligar al modelo a cerrar con una respuesta de texto
c = ClienteFalso([
    Respuesta(llamadas=[Llamada(name="run_sql", args={"query": "a"})]),
    Respuesta(llamadas=[Llamada(name="run_sql", args={"query": "b"})]),
    Respuesta(texto="Resumen final."),
])
r = conversar(c, max_pasos=3)
check("en el último paso pide la respuesta final sin herramientas", r == "Resumen final." and hasattr(c.llamadas[0].config, "tools") and not hasattr(c.llamadas[-1].config, "tools"))

# ------------------------------------------------------------- 4) cuota agotada y modelo de respaldo
c = ClienteFalso([ErrorApi(429, "RESOURCE_EXHAUSTED"), Respuesta(texto="Con el respaldo.")])
r = conversar(c)
check("con cuota agotada prueba el modelo de respaldo", r == "Con el respaldo." and [x.model for x in c.llamadas] == ["principal", "respaldo"])

c = ClienteFalso([ErrorApi(429, "RESOURCE_EXHAUSTED", "Quota exceeded, plan details SECRETO-INTERNO"), ErrorApi(429, "RESOURCE_EXHAUSTED")])
e = falla(c)
check("si se acaba la cuota en ambos modelos, avisa con mensaje claro", e is not None and e.tipo == "cuota" and e.mensaje == llm.MENSAJES["cuota"])
check("el mensaje al usuario no filtra detalles técnicos", e is not None and "SECRETO-INTERNO" not in e.mensaje and "429" not in e.mensaje)

c = ClienteFalso([ErrorApi(503, "UNAVAILABLE"), Respuesta(texto="Con el respaldo.")])
r = conversar(c)
check("con el servicio saturado prueba el modelo de respaldo", r == "Con el respaldo." and [x.model for x in c.llamadas] == ["principal", "respaldo"])

c = ClienteFalso([ErrorApi(404, "NOT_FOUND"), Respuesta(texto="Con el respaldo.")])
r = conversar(c)
check("si el modelo principal no existe prueba el de respaldo", r == "Con el respaldo.")

# reintentos ante saturación: espera y vuelve a intentar con el mismo modelo antes de usar el respaldo
llm.ESPERA_REINTENTO = (0, 0)
c = ClienteFalso([ErrorApi(503, "UNAVAILABLE"), ErrorApi(503, "UNAVAILABLE"), Respuesta(texto="Al tercer intento.")])
r = conversar(c)
check("si el servicio está saturado reintenta con el mismo modelo", r == "Al tercer intento." and [x.model for x in c.llamadas] == ["principal"] * 3)

c = ClienteFalso([ErrorApi(503, "UNAVAILABLE")] * 3 + [Respuesta(texto="Con el respaldo.")])
r = conversar(c)
check("tras los reintentos usa el modelo de respaldo", r == "Con el respaldo." and c.llamadas[-1].model == "respaldo")

c = ClienteFalso([ErrorApi(503, "UNAVAILABLE")] * 6)
e = falla(c)
check("si todo sigue saturado, avisa con mensaje claro", e is not None and e.tipo == "saturado" and len(c.llamadas) == 6)
llm.ESPERA_REINTENTO = ()

c = ClienteFalso([ErrorApi(429, "RESOURCE_EXHAUSTED"), ErrorApi(503, "UNAVAILABLE"), Respuesta(texto="Con el tercero.")])
r = conversar(c, modelos=("uno", "dos", "tres"))
check("con tres modelos prueba el siguiente hasta que uno responde", r == "Con el tercero." and [x.model for x in c.llamadas] == ["uno", "dos", "tres"])

# ------------------------------------------------------------- 5) otras fallas
casos = [
    ("sin conexión", ConnectionError("Name or service not known"), "conexion"),
    ("tiempo agotado", TimeoutError("timed out"), "conexion"),
    ("clave inválida", ErrorApi(400, "INVALID_ARGUMENT", "API key not valid. Please pass a valid API key."), "clave"),
    ("permiso denegado", ErrorApi(403, "PERMISSION_DENIED"), "clave"),
    ("servicio saturado", ErrorApi(503, "UNAVAILABLE"), "saturado"),
    ("modelo inexistente", ErrorApi(404, "NOT_FOUND"), "modelo"),
    ("falla desconocida", ValueError("algo raro"), "otro"),
]
for nombre, exc, tipo in casos:
    e = falla(ClienteFalso([exc, exc]))  # dos intentos: principal y respaldo
    check(f"{nombre} -> mensaje '{tipo}'", e is not None and e.tipo == tipo and e.mensaje == llm.MENSAJES[tipo], getattr(e, "tipo", None))

e = falla(ClienteFalso([Respuesta(texto="")]))
check("respuesta vacía -> mensaje claro", e is not None and e.tipo == "vacia")

# ------------------------------------------------------------- 6) la clave nunca se muestra
llm.crear_cliente("CLAVE-SECRETA-123")
check("crea el cliente con la clave recibida", claves_creadas == ["CLAVE-SECRETA-123"])
e = falla(ClienteFalso([RuntimeError("falló la llamada con key=CLAVE-SECRETA-123")]))
check("si la clave aparece en un error, se tapa", e is not None and "CLAVE-SECRETA-123" not in e.detalle and "***" in e.detalle, getattr(e, "detalle", ""))
check("el mensaje al usuario nunca incluye la clave", e is not None and "CLAVE-SECRETA-123" not in e.mensaje)

print("\n" + ("TODO OK: la capa de IA se comporta como se espera." if ok else "HAY FALLAS: pégame esta salida completa."))
sys.exit(0 if ok else 1)
