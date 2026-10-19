"""Paleta, estilos y etiquetas de la interfaz (tonos azules).
Dos ideas importantes:
 - Los colores de marca son azules. Los colores de ESTADO (rojo, ámbar, verde) se quedan porque llevan significado.
 - Los códigos internos del diagnóstico (QUIEBRE, EN_TRANSITO...) se muestran al usuario con ETIQUETAS en lenguaje de KAM."""
import math
from string import Template

NOMBRE_APP = "Casa Lumina"

MARINO = "#0B2A4A"
AZUL_OSCURO = "#12406F"
AZUL = "#1D63AE"
CIAN = "#2EC4E6"
CELESTE = "#BFE3F7"
CELESTE_SUAVE = "#E8F4FB"
HIELO = "#F4F8FB"
FONDO = HIELO
BORDE = "#D5E3EE"
TEXTO = "#0E2236"
GRIS = "#64748B"
ROJO = "#C8453B"
AMBAR = "#E0A526"
MORADO = "#7A5C99"
VERDE = "#3BAA6B"
TURQUESA = "#2A9D8F"
AZUL_MEDIO = "#5B8DB8"

FUENTE = "Poppins, Segoe UI, system-ui, sans-serif"
COLORWAY = [AZUL, CIAN, AZUL_MEDIO, "#9CC9E6", "#7C93AB", MARINO, AMBAR, TURQUESA]

# Colores con significado: el mismo estado se ve igual en todos los gráficos
COLOR_SITUACION = {
    "QUIEBRE": ROJO,
    "RIESGO_QUIEBRE": AMBAR,
    "CAIDA_POR_QUIEBRE_RECIENTE": "#E07A5F",
    "CAIDA_CON_INVENTARIO": "#D9822B",
    "POSIBLE_INV_FANTASMA": MORADO,
    "SIN_ROTACION": GRIS,
    "SOBREINVENTARIO": TURQUESA,
    "ACELERANDO": VERDE,
    "ESTABLE": AZUL_MEDIO,
    "BAJO_VOLUMEN": "#B8C4D0",
    "INV_DESACTUALIZADO": "#9CA3AF",
}
COLOR_PIPELINE = {
    "EN_TRANSITO": VERDE,
    "PEDIDO_ABIERTO": AZUL_MEDIO,
    "STOCK_EN_CEDIS_SIN_ENVIO": AMBAR,
    "SIN_PIPELINE": ROJO,
}

# Lenguaje de KAM: código interno -> lo que ve el usuario (en gráficos, tablas y respuestas del asistente)
ETIQUETAS = {
    # situación del producto en tienda
    "QUIEBRE": "Sin producto en tienda (quiebre)",
    "RIESGO_QUIEBRE": "Por agotarse",
    "CAIDA_POR_QUIEBRE_RECIENTE": "Venta a la baja por falta de producto",
    "CAIDA_CON_INVENTARIO": "Venta a la baja con producto en tienda",
    "POSIBLE_INV_FANTASMA": "Inventario que parece no estar en anaquel",
    "SIN_ROTACION": "Producto sin movimiento",
    "SOBREINVENTARIO": "Exceso de inventario",
    "ACELERANDO": "Venta en aceleración",
    "BAJO_VOLUMEN": "Poca venta para opinar",
    "INV_DESACTUALIZADO": "Inventario sin actualizar",
    "ESTABLE": "Sin alertas",
    # quién repone
    "EN_TRANSITO": "Viene en camino",
    "PEDIDO_ABIERTO": "Hay pedido abierto",
    "STOCK_EN_CEDIS_SIN_ENVIO": "Hay en CEDIS pero no llega a la tienda",
    "SIN_PIPELINE": "Nadie lo está reponiendo",
}

# Nombres de columna conocidos -> encabezado legible (se usa en tarjetas y tablas)
COLUMNAS = {
    "situacion": "Situación",
    "pipeline": "Reposición",
    "series": "Combinaciones tienda-producto",
    "series_en_quiebre": "Combinaciones sin producto en tienda",
    "series_en_riesgo": "Combinaciones por agotarse",
    "posibles_fantasma": "Inventario que parece no estar en anaquel",
    "venta_diaria_en_riesgo_mxn": "Venta diaria en riesgo (MXN)",
    "valor_mxn": "Venta (MXN)",
    "dias_inv": "Días de cobertura",
    "dias_sin_venta": "Días sin venta",
    "inv_hoy": "Inventario hoy",
    "nombre_tienda": "Tienda",
    "nombre": "Tienda",
    "tienda": "Código de tienda",
    "ean": "Producto (código de barras)",
    "marca": "Marca",
    "cadena": "Cadena",
    "semana": "Semana",
}

PREGUNTAS_RAPIDAS = {
    "Dónde actuar": [
        "¿Dónde estoy perdiendo venta por falta de producto y por qué?",
        "¿Qué tiendas tienen inventario pero no venden?",
        "¿Qué productos están cayendo aunque hay producto en tienda?",
        "¿Qué faltantes se explican porque hay producto en CEDIS que no llega a la tienda?",
    ],
    "Ventas": [
        "¿Cómo vamos por cadena este mes contra el mes anterior?",
        "Gráfico de venta semanal por cadena",
        "¿Qué marcas crecen y cuáles caen?",
    ],
    "Tableros": [
        "Dame un tablero de salud de inventario por cadena",
        "Dame un tablero de ventas por marca y categoría",
    ],
}


def etiqueta(valor):
    """Código interno -> etiqueta de KAM (si no es un código conocido, lo devuelve igual)."""
    return ETIQUETAS.get(valor, valor)


def etiquetar_valores(df):
    """Copia del DataFrame con los códigos internos traducidos a etiquetas de KAM (solo valores)."""
    out = df.copy()
    for c in out.columns:
        if getattr(out[c].dtype, "kind", "O") in "OSU":  # texto (object o string), no números ni fechas
            out[c] = out[c].map(lambda v: ETIQUETAS.get(v, v) if isinstance(v, str) else v)
    return out


def encabezado(nombre) -> str:
    """Nombre de columna -> encabezado legible."""
    n = str(nombre)
    if n.lower() in COLUMNAS:
        return COLUMNAS[n.lower()]
    return n.replace("_", " ").capitalize().replace(" mxn", " (MXN)")


def encabezados(df):
    """Copia del DataFrame con los nombres de columna legibles (para mostrar, no para graficar)."""
    return df.rename(columns={c: encabezado(c) for c in df.columns})


def glosario_para_modelo() -> str:
    """Texto para el prompt del modelo: cómo debe llamar a cada código al hablar con el usuario."""
    return "\n".join(f"- {k} -> «{v}»" for k, v in ETIQUETAS.items())


def mapa_colores(df, x, color):
    """Si la columna de color (o el eje x) trae situaciones o pipelines, usa su color fijo (devuelve {código: color})."""
    for c in (color, x):
        if c is not None and c in df.columns:
            vals = set(df[c].dropna().astype(str))
            for mapa in (COLOR_SITUACION, COLOR_PIPELINE):
                if vals and vals <= set(mapa):
                    return {k: v for k, v in mapa.items() if k in vals}
    return None


def _hex(cx, cy, r, fill="none", stroke="none", sw=0, op=1.0):
    pts = " ".join(
        f"{cx + r * math.cos(math.radians(60 * i - 30)):.1f},{cy + r * math.sin(math.radians(60 * i - 30)):.1f}"
        for i in range(6)
    )
    return f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" fill-opacity="{op}"/>'


def hex_svg() -> str:
    """Racimo de hexágonos decorativo en azules."""
    figs = [
        _hex(248, 48, 40, fill=CIAN),
        _hex(176, 92, 34, stroke=CIAN, sw=1.5),
        _hex(262, 124, 24, fill=CELESTE),
        _hex(120, 58, 16, fill=AZUL),
        _hex(84, 108, 12, fill=CELESTE, op=0.9),
        _hex(204, 22, 10, stroke=CELESTE, sw=1.5),
        _hex(150, 130, 14, fill=CIAN, op=0.55),
    ]
    return '<svg viewBox="0 0 300 160" xmlns="http://www.w3.org/2000/svg">' + "".join(figs) + "</svg>"


_CSS = Template("""
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
html, body, .stApp, [data-testid="stMarkdownContainer"], button, input, textarea { font-family: 'Poppins', 'Segoe UI', system-ui, sans-serif; }
.stApp { background: $FONDO; }
header[data-testid="stHeader"] { background: transparent; }
[data-testid="stDecoration"] { display:none; }
[data-testid="stChatMessageAvatarAssistant"] { background: $AZUL_OSCURO; color: $CIAN; }
[data-testid="stChatMessageAvatarUser"] { background: $CELESTE; color: $AZUL_OSCURO; }
.block-container { padding-top: 1.4rem; max-width: 1180px; }

.vs-hero { display:flex; align-items:center; justify-content:space-between; gap:16px; background: linear-gradient(120deg, $MARINO 0%, $AZUL_OSCURO 100%); border-radius: 22px; padding: 26px 34px; margin-bottom: 18px; overflow:hidden; }
.vs-hero-txt { color: $CELESTE_SUAVE; max-width: 660px; }
.vs-kicker { letter-spacing:.18em; font-size:.72rem; color:$CIAN; font-weight:600; }
.vs-hero h1 { color:#fff; font-size:2rem; margin:.2rem 0 .3rem 0; padding:0; font-weight:700; line-height:1.15; }
.vs-hero p { color:$CELESTE_SUAVE; opacity:.9; margin:0 0 .8rem 0; font-size:.95rem; }
.vs-chips span { display:inline-block; background:rgba(46,196,230,.14); color:$CELESTE; border:1px solid rgba(46,196,230,.4); border-radius:999px; padding:3px 12px; font-size:.75rem; margin:0 8px 6px 0; }
.vs-hero-art svg { height:150px; width:auto; }

section[data-testid="stSidebar"] { background: $MARINO; }
section[data-testid="stSidebar"] * { color: $CELESTE_SUAVE; }
section[data-testid="stSidebar"] .stButton > button { width:100%; text-align:left; background: rgba(232,244,251,.06); border:1px solid rgba(232,244,251,.2); border-radius:12px; font-size:.82rem; padding:.45rem .7rem; line-height:1.25; }
section[data-testid="stSidebar"] .stButton > button:hover { border-color:$CIAN; background: rgba(46,196,230,.14); }
section[data-testid="stSidebar"] hr { border-color: rgba(232,244,251,.15); }
.vs-brand { font-weight:700; font-size:1.1rem; letter-spacing:.02em; padding:.2rem 0 .6rem 0; }
.vs-brand b { color:$CIAN; }

[data-testid="stChatMessage"] { background:#fff; border:1px solid $BORDE; border-radius:16px; padding:14px 16px; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { background:$CELESTE_SUAVE; }
[data-testid="stChatInput"] { border-radius:18px; border:1.5px solid $AZUL; }
[data-testid="stExpander"] { border:1px solid $BORDE; border-radius:12px; background:#fff; }
[data-testid="stPlotlyChart"] { background:#fff; border:1px solid $BORDE; border-radius:16px; padding:8px; }

.vs-kpis { display:grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap:12px; margin:6px 0 14px 0; }
.vs-kpi { background:#fff; border:1px solid $BORDE; border-left:5px solid $CIAN; border-radius:14px; padding:14px 16px; }
.vs-kpi-v { font-size:1.65rem; font-weight:700; color:$AZUL_OSCURO; line-height:1.15; }
.vs-kpi-l { font-size:.74rem; color:$GRIS; text-transform:uppercase; letter-spacing:.06em; margin-top:2px; }
.vs-vis-t { font-weight:600; color:$AZUL_OSCURO; margin:4px 0 2px 0; font-size:1rem; }
.vs-sec { font-weight:700; color:$AZUL_OSCURO; font-size:1.15rem; margin:18px 0 6px 0; }
""")


def css() -> str:
    return "<style>" + _CSS.substitute(
        FONDO=FONDO, MARINO=MARINO, AZUL_OSCURO=AZUL_OSCURO, AZUL=AZUL, CIAN=CIAN, CELESTE=CELESTE,
        CELESTE_SUAVE=CELESTE_SUAVE, BORDE=BORDE, GRIS=GRIS,
    ) + "</style>"
