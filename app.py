"""Casa Lumina · Sell Out & Inventarios (Streamlit): chat con IA (Gemini) y un Tablero que funciona SIN IA.

La app funciona aunque falte la clave de Gemini o se acabe la cuota gratuita: el Tablero siempre está disponible.
Todos los datos son ficticios (ver generar_datos_sinteticos.py).
"""
import datetime as dt
import logging
import os
from pathlib import Path

import pandas as pd
import streamlit as st

import llm
import tema
import visuales
from agent import CFG, ask, build_system, connect

log = logging.getLogger("casa_lumina.app")
ROOT = Path(__file__).parent


def _version() -> tuple:
    try:
        return tuple(int(p) for p in st.__version__.split(".")[:2])
    except Exception:
        return (0, 0)


# "⬢" no es un emoji que Streamlit reconozca (lo intenta cargar como imagen y falla):
# se usa el ícono nativo en versiones nuevas y un emoji estándar en las viejas.
ICONO = ":material/hexagon:" if _version() >= (1, 40) else "🔷"

st.set_page_config(page_title=f"{tema.NOMBRE_APP} · Sell Out & Inventarios", page_icon=ICONO, layout="wide")
st.markdown(tema.css(), unsafe_allow_html=True)

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
AVATAR = ICONO

MSG_SIN_IA = (
    "El asistente de IA todavía no está activo en esta versión de la app. "
    "Mientras tanto, el **Tablero** ya funciona y no necesita IA: ábrelo arriba, en la barra lateral."
)


# ---------------------------------------------------------------- arranque
def asegurar_datos():
    """Si la carpeta data/ está vacía, genera los datos ficticios (así la app arranca aunque no se hayan subido)."""
    if list((ROOT / "data" / "sellout").glob("*.parquet")):
        return
    import generar_datos_sinteticos as gen

    gen.escribir(gen.simular())


@st.cache_resource(show_spinner="Preparando los datos de ejemplo (solo la primera vez)...")
def boot():
    asegurar_datos()
    con = connect()
    return con, build_system(con)


def _leer_clave() -> str:
    """La clave vive en los secretos de la plataforma (st.secrets) o en la variable de entorno GEMINI_API_KEY."""
    try:
        valor = st.secrets["GEMINI_API_KEY"]
    except Exception:
        valor = os.environ.get("GEMINI_API_KEY", "")
    valor = str(valor or "").strip()
    return "" if valor.lower().startswith("pega") else valor  # ignora la clave de ejemplo


@st.cache_resource(show_spinner=False)
def cliente_ia(clave: str):
    return llm.crear_cliente(clave)


con, system = boot()
client, client_error = None, ""
_clave = _leer_clave()
if _clave:
    try:
        client = cliente_ia(_clave)
    except Exception as e:  # sin cliente, el Tablero sigue funcionando
        client_error = str(e)
        log.warning("No pude crear el cliente de IA: %s", llm._tapar(e))

if "messages" not in st.session_state:
    st.session_state.messages = []  # historial de texto que se le manda al modelo
if "view" not in st.session_state:
    st.session_state.view = []  # lo que se pinta en pantalla
if "n_preguntas" not in st.session_state:
    st.session_state.n_preguntas = 0


@st.cache_resource
def _contador_dia() -> dict:
    return {"dia": None, "n": 0}


def hay_cupo_dia() -> bool:
    """Tope diario de toda la app, para que nadie agote la cuota gratuita."""
    c = _contador_dia()
    hoy = dt.date.today()
    if c["dia"] != hoy:
        c["dia"], c["n"] = hoy, 0
    return c["n"] < CFG.get("max_preguntas_dia", 150)


# ---------------------------------------------------------------- datos
@st.cache_data(ttl=300, show_spinner=False)
def frescura() -> dict:
    cur = con.cursor()
    out = {}
    for tabla, d in CFG["datasets"].items():
        if d.get("date_col"):
            out[tabla] = cur.execute(f'SELECT max("{d["date_col"]}") FROM {tabla}').fetchone()[0]
    return out


def _fecha(v) -> str:
    d = pd.Timestamp(v)
    return f"{d.day} {MESES[d.month - 1]} {d.year}"


@st.cache_data(ttl=600, show_spinner=False)
def consulta(sql: str) -> pd.DataFrame:
    return con.cursor().execute(sql).df()


@st.cache_resource(show_spinner=False)
def diag_cache() -> bool:
    """Congela el diagnóstico en una tabla para que el tablero cargue rápido (el chat sigue usando la vista)."""
    con.cursor().execute("CREATE OR REPLACE TABLE diag_cache AS SELECT * FROM v_diag_sku_tienda")
    return True


# ---------------------------------------------------------------- piezas de interfaz
def hero():
    try:
        f = frescura()
    except Exception:
        f = {}
    chips = "<span>Datos ficticios de Casa Lumina</span>"
    if f.get("sellout") is not None:
        chips += f"<span>Ventas al {_fecha(f['sellout'])}</span>"
    if f.get("inventarios") is not None:
        chips += f"<span>Inventario al {_fecha(f['inventarios'])}</span>"
    chips += "<span>Cifras en MXN sin IVA</span>"
    st.markdown(
        '<div class="vs-hero"><div class="vs-hero-txt"><div class="vs-kicker">VENTAS E INVENTARIO EN TIENDA</div>'
        "<h1>Pregúntale a tus datos</h1>"
        "<p>Dónde se vende, dónde falta producto y qué hacer, en español y con gráficos.</p>"
        f'<div class="vs-chips">{chips}</div></div><div class="vs-hero-art">{tema.hex_svg()}</div></div>',
        unsafe_allow_html=True,
    )


def _sin_latex(texto: str) -> str:
    """Streamlit interpreta dos signos $ como fórmula matemática: se escapan para que los MXN salgan bien."""
    return texto.replace("$", "\\$")


def pintar(texto, sqls, vis, clave):
    for j, (spec, df) in enumerate(vis):
        visuales.mostrar(spec, df, f"{clave}_{j}")
    st.markdown(_sin_latex(texto))
    if sqls:
        with st.expander("Ver SQL (para auditar)"):
            for q in sqls:
                st.code(q, language="sql")


def vista_chat():
    activo = client is not None
    if not st.session_state.view:
        with st.chat_message("assistant", avatar=AVATAR):
            if activo:
                st.markdown(
                    "Hola. Pregúntame por ventas, inventario o faltantes de producto. También puedo graficar: pídeme "
                    "**«gráfico de venta semanal por cadena»** o **«un tablero de salud de inventario»**."
                )
            else:
                st.markdown(MSG_SIN_IA)
    for i, (rol, texto, sqls, vis) in enumerate(st.session_state.view):
        with st.chat_message(rol, avatar=AVATAR if rol == "assistant" else None):
            pintar(texto, sqls, vis, f"h{i}")

    entrada = st.chat_input("Pregunta sobre ventas, inventario, faltantes...", disabled=not activo)
    pregunta = st.session_state.pop("pendiente", None) or entrada
    if not pregunta:
        return
    if not activo:
        st.info(MSG_SIN_IA)
        return
    if st.session_state.n_preguntas >= CFG.get("max_preguntas_sesion", 12):
        st.warning(
            "Llegaste al límite de preguntas de esta sesión (lo pongo para cuidar la cuota gratuita de la IA). "
            "Puedes seguir explorando el Tablero, o recargar la página para empezar de nuevo."
        )
        return
    if not hay_cupo_dia():
        st.warning("La demo alcanzó su límite diario de preguntas a la IA. Vuelve mañana, o explora el Tablero, que no la usa.")
        return

    st.session_state.view.append(("user", pregunta, [], []))
    with st.chat_message("user"):
        st.markdown(_sin_latex(pregunta))
    st.session_state.n_preguntas += 1
    _contador_dia()["n"] += 1

    with st.chat_message("assistant", avatar=AVATAR):
        ok = True
        try:
            with st.spinner("Consultando tus datos..."):
                texto, sqls, vis = ask(client, con.cursor(), st.session_state.messages[-10:], pregunta, system)
        except llm.ErrorLLM as e:  # cuota agotada, sin conexión, clave inválida...
            ok, texto, sqls, vis = False, f"⚠️ {e.mensaje}", [], []
        except Exception:  # cualquier otra falla: mensaje amable, detalle solo al log
            log.exception("Falla inesperada al responder")
            ok, texto, sqls, vis = False, "⚠️ " + llm.MENSAJES["otro"], [], []
        pintar(texto, sqls, vis, f"h{len(st.session_state.view)}")
    if ok:  # una respuesta fallida no entra al historial que se le manda al modelo
        st.session_state.messages += [
            {"role": "user", "content": pregunta},
            {"role": "assistant", "content": texto},
        ]
    st.session_state.view.append(("assistant", texto, sqls, vis))


def _base(cadenas) -> str:
    """CTE con el diagnóstico enriquecido con catálogos, filtrado por cadena."""
    T = CFG["tablero"]
    filtro = ""
    if cadenas:
        lista = ", ".join("'" + c.replace("'", "''") + "'" for c in cadenas)
        filtro = f"WHERE cadena IN ({lista})"
    return (
        f"WITH base0 AS (SELECT x.*, coalesce(t.{T['tienda_cadena']}, 'SIN CATALOGO') AS cadena, "
        f"t.{T['tienda_nombre']} AS nombre_tienda, coalesce(p.{T['eans_marca']}, 'SIN CATALOGO') AS marca "
        f"FROM diag_cache x "
        f"LEFT JOIN cat_tiendas t ON x.tienda = t.{T['tienda_llave']} "
        f"LEFT JOIN cat_eans p ON x.ean = p.{T['eans_llave']}), "
        f"base AS (SELECT * FROM base0 {filtro}) "
    )


def _sql_semanal(cadenas) -> str:
    C, T = CFG["cols"], CFG["tablero"]
    fecha, tienda, valor = f'"{C["fecha"]}"', f'"{C["tienda"]}"', f'"{C["valor"]}"'
    filtro = ""
    if cadenas:
        lista = ", ".join("'" + c.replace("'", "''") + "'" for c in cadenas)
        filtro = f"AND coalesce(t.{T['tienda_cadena']}, 'SIN CATALOGO') IN ({lista})"
    return (
        f"WITH f AS (SELECT max({fecha}) AS hoy FROM sellout) "
        f"SELECT date_trunc('week', s.{fecha}) AS semana, coalesce(t.{T['tienda_cadena']}, 'SIN CATALOGO') AS cadena, "
        f"round(sum(s.{valor}), 0) AS valor_mxn "
        f"FROM sellout s CROSS JOIN f LEFT JOIN cat_tiendas t ON s.{tienda} = t.{T['tienda_llave']} "
        f"WHERE s.{fecha} >= date_trunc('week', f.hoy) - INTERVAL 26 WEEK "
        f"AND s.{fecha} < date_trunc('week', f.hoy) {filtro} GROUP BY 1, 2 ORDER BY 1"
    )


def _seccion(titulo):
    st.markdown(f'<div class="vs-sec">{titulo}</div>', unsafe_allow_html=True)


def _intentar(spec, sql, clave):
    try:
        visuales.mostrar(spec, consulta(sql), clave)
    except Exception as e:
        log.warning("No pude armar «%s»: %s", spec.get("title"), e)
        st.warning(f"No pude armar «{spec.get('title')}». Prueba con «Actualizar datos».")


def vista_tablero():
    T = CFG["tablero"]
    with st.spinner("Calculando el diagnóstico (solo la primera vez, o al actualizar)..."):
        try:
            diag_cache()
        except Exception:
            log.exception("No pude calcular el diagnóstico")
            st.error("No pude calcular el diagnóstico. Intenta recargar la página.")
            return

    c1, c2 = st.columns([4, 1])
    try:
        todas = consulta(
            f"SELECT DISTINCT {T['tienda_cadena']} AS cadena FROM cat_tiendas "
            f"WHERE {T['tienda_cadena']} IS NOT NULL ORDER BY 1"
        )["cadena"].tolist()
    except Exception:
        todas = []
    with c1:
        cadenas = st.multiselect("Cadena", todas, placeholder="Todas las cadenas")
    with c2:
        st.write("")
        if st.button("Actualizar datos"):
            diag_cache.clear()
            consulta.clear()
            frescura.clear()
            st.rerun()

    base = _base(cadenas)
    en_riesgo = "round(sum(vel_28 * v28 / nullif(u28, 0)), 0)"

    _seccion("Resumen")
    _intentar(
        {"kind": "kpi", "title": None, "format": "auto"},
        base + "SELECT "
        "count(*) FILTER (WHERE situacion = 'QUIEBRE') AS series_en_quiebre, "
        "coalesce(round(sum(vel_28 * v28 / nullif(u28, 0)) FILTER (WHERE situacion = 'QUIEBRE'), 0), 0) "
        "AS venta_diaria_en_riesgo_mxn, "
        "count(*) FILTER (WHERE situacion = 'RIESGO_QUIEBRE') AS series_en_riesgo, "
        "count(*) FILTER (WHERE situacion = 'POSIBLE_INV_FANTASMA') AS posibles_fantasma FROM base",
        "t_kpi",
    )

    _seccion("Salud del inventario")
    a, b = st.columns(2)
    with a:
        _intentar(
            {"kind": "barh", "title": "Combinaciones tienda-producto por situación", "x": "situacion", "y": ["series"]},
            base + "SELECT situacion, count(*) AS series FROM base GROUP BY 1 ORDER BY 2 DESC",
            "t_sit",
        )
    with b:
        _intentar(
            {"kind": "donut", "title": "¿Quién repone lo que falta en tienda?", "x": "pipeline", "y": ["series"]},
            base + "SELECT pipeline, count(*) AS series FROM base WHERE situacion = 'QUIEBRE' GROUP BY 1 ORDER BY 2 DESC",
            "t_pipe",
        )

    _seccion("Ventas")
    _intentar(
        {"kind": "line", "title": "Venta semanal por cadena (MXN, últimas 26 semanas completas)",
         "x": "semana", "y": ["valor_mxn"], "color": "cadena", "format": "mxn"},
        _sql_semanal(cadenas),
        "t_semanal",
    )

    _seccion("Dónde actuar")
    a, b = st.columns(2)
    with a:
        _intentar(
            {"kind": "table", "title": "Tiendas con más venta en riesgo por falta de producto"},
            base + "SELECT tienda, max(nombre_tienda) AS nombre, max(cadena) AS cadena, count(*) AS series_en_quiebre, "
            f"{en_riesgo} AS venta_diaria_en_riesgo_mxn FROM base WHERE situacion = 'QUIEBRE' "
            "GROUP BY 1 ORDER BY 5 DESC NULLS LAST LIMIT 15",
            "t_top",
        )
    with b:
        _intentar(
            {"kind": "bar", "title": "Salud del inventario por marca", "x": "marca", "y": ["series"],
             "color": "situacion", "stacked": True},
            base + "SELECT marca, situacion, count(*) AS series FROM base GROUP BY 1, 2 ORDER BY 1",
            "t_marca",
        )


# ---------------------------------------------------------------- barra lateral
if st.session_state.pop("ir_chat", False):
    st.session_state["vista"] = "Chat"

with st.sidebar:
    st.markdown(f'<div class="vs-brand"><b>⬢</b> {tema.NOMBRE_APP}</div>', unsafe_allow_html=True)
    logo = ROOT / "assets" / "logo.png"
    if logo.exists():
        st.image(str(logo))
    vista = st.radio("Vista", ["Chat", "Tablero"], key="vista", horizontal=True, label_visibility="collapsed")
    st.markdown("##### Preguntas rápidas")
    for grupo, preguntas in tema.PREGUNTAS_RAPIDAS.items():
        st.caption(grupo)
        for i, q in enumerate(preguntas):
            if st.button(q, key=f"qr_{grupo}_{i}"):
                st.session_state["pendiente"] = q
                st.session_state["ir_chat"] = True
                st.rerun()
    st.divider()
    if st.button("Nueva conversación", key="reset"):
        st.session_state.messages, st.session_state.view = [], []
        st.rerun()
    st.caption("Cada número sale de una consulta a los datos. Abre «Ver SQL» en cada respuesta si quieres auditarla. Datos ficticios.")

hero()
if vista == "Chat":
    vista_chat()
else:
    vista_tablero()
