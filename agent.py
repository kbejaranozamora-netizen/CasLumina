"""Agente text-to-SQL sobre parquets: DuckDB ejecuta las consultas, Gemini las escribe y explica el resultado.

División de trabajo (es la respuesta a «qué hace la IA y qué no»):
 - La IA traduce la pregunta a SQL, elige el gráfico y explica el resultado con prudencia.
 - Los NÚMEROS los calcula siempre DuckDB. El modelo no hace cuentas ni inventa cifras.
 - Todo lo que toca los datos pasa por los guardrails de _ejecutar (un solo SELECT, sin leer archivos, con tope y timeout).
"""
import re
import threading
import unicodedata
from pathlib import Path

import duckdb
import yaml

import llm
import tema

ROOT = Path(__file__).parent
CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))

# Defensa extra: el SELECT puede intentar leer archivos arbitrarios.
BLOCK = re.compile(
    r"\b(read_\w+|glob|pragma|attach|detach|copy|install|load|export)\b"
    r"|\.(parquet|csv|json|db)\b",
    re.I,
)

RULES = """Eres el asistente de sell out e inventarios de Casa Lumina, una empresa ficticia de consumo masivo (hogar). Hablas con KAMs y analistas comerciales que NO saben SQL. Respondes en español, directo, claro y en lenguaje de negocio.

REGLAS
- Nunca inventes números: todo sale de run_sql. Si el SQL falla, lee el error, corrige y reintenta (máximo 2 veces).
- Antes de hablar de períodos recientes, revisa en RESUMEN DE DATOS hasta qué fecha llega la data y menciónalo; no asumas que es hoy.
- Si la pregunta es ambigua (ej. «ventas» = ¿unidades o valor?), elige la interpretación más razonable, dila en una línea y responde.
- Si la pregunta no tiene que ver con ventas, inventario o los datos de esta app, di amablemente que no puedes ayudar con eso y ofrece 2 preguntas que sí puedes contestar.
- Si los datos no alcanzan para responder (precio, promociones, exhibición, competencia), dilo claramente.
- Prefiere agregar en SQL; nunca pidas filas crudas masivas. Usa LIMIT y ORDER BY.
- Para comparar períodos, compara períodos equivalentes (mismos días) y avísalo.
- NUNCA muestres al usuario SQL, nombres de columnas ni códigos internos (el botón «Ver SQL» ya existe para quien quiera auditar). Al hablar, usa siempre el LENGUAJE DE KAM de abajo.
- Termina con el insight principal en 1 o 2 frases y, si aplica, de 1 a 3 acciones concretas ordenadas por impacto.

LENGUAJE DE KAM (código interno -> cómo lo dices al usuario)
{glosario}
- «series» o «combinaciones» = pares tienda-producto. EAN = producto (código de barras). CEDIS = centro de distribución de la cadena.

DATOS
- Cortes por cadena, formato, tipo de formato, región, estado o ciudad: cat_tiendas (ID_OUTLET = tienda; la cadena está en RETAILER). Cortes por marca, categoría, segmento o presentación: cat_eans (EAN).
- Usa LEFT JOIN a los catálogos. Si una tienda o EAN no aparece en el catálogo, no lo descartes: agrúpalo como 'SIN CATALOGO' y menciónalo.
- Los valores (V) están en pesos mexicanos sin IVA. Preséntalos como MXN y menciona que no incluyen IVA cuando sea relevante.
- Tablas crudas: sellout (columnas "DATE", ID_RETAILER, ID_OUTLET, EAN, U, V) e inventarios (columnas "DATE", ID_RETAILER, ID_OUTLET, EAN, INV_TIENDA, INV_TRANSITO, INV_CEDIS, UNID_ORDENADAS). Escribe "DATE" siempre entre comillas dobles. Las vistas v_base, v_semanal y v_diag_sku_tienda usan tienda, fecha, ean.
- Las vistas de diagnóstico solo cubren los últimos días configurados. Para historia larga (meses o años) consulta sellout directo.

DIAGNÓSTICO (cuando pregunten «qué está pasando», «por qué cayó», «cómo vamos»):
1. Parte de v_diag_sku_tienda (columna situacion) y v_semanal (tendencias). Agrega por la dimensión pedida (cadena, marca, tienda...) con joins a los catálogos. No recalcules a mano lo que ya viene en las vistas.
2. Estructura la respuesta en tres bloques cortos: (a) Qué muestran los datos (cifras), (b) Posibles causas, ordenadas por evidencia, (c) Qué no se puede saber con esta data (precio, promo, exhibición, competencia, cambios de surtido) y qué revisar en campo.
3. Distingue venta perdida por falta de producto (inventario en cero y la venta cae) de caída de demanda (hay producto y la venta cae). En faltantes revisa la columna pipeline: «Viene en camino» o «Hay pedido abierto» es temporal, «Hay en CEDIS pero no llega a la tienda» es un problema de distribución de la cadena (escalar con la cadena), «Nadie lo está reponiendo» es prioridad máxima. Pondera por valor: prioriza lo que más dinero mueve, no lo que más filas tiene.
4. No afirmes causalidad: usa «es consistente con» o «sugiere». Una correlación entre inventario y venta puede ir en ambas direcciones.
5. Compara semanas completas (dias_con_data = 7). Si la situación es «Inventario sin actualizar» o la data termina antes de hoy, adviértelo. «Poca venta para opinar» significa que no hay unidades suficientes para hablar de tendencia: no inventes una.
6. Cierra con 1 a 3 acciones concretas ordenadas por impacto.

VISUALES (herramienta show_visual, máximo 4 por respuesta)
- Úsala cuando una imagen comunique mejor que texto: tendencias (line o area), rankings (barh, ordenado de mayor a menor, 10 a 15 elementos), comparativos (bar), composición (bar apilado, o donut solo con 6 partes o menos), tarjetas de resumen (kpi: la consulta devuelve UNA fila y cada columna es una tarjeta).
- Si piden un «tablero» o «dashboard», combina 1 kpi con 2 o 3 gráficos que cuenten una historia.
- No grafiques 1 o 2 números: dilos en texto. Ordena y filtra en SQL, y usa alias legibles (valor_mxn, series_en_quiebre). Para tiempo usa semanas completas.
- Después de mostrar las visuales, interpreta en 2 a 4 frases lo más importante. No repitas todos los números.
"""


# ---------- vistas ----------
def _norm(nombre) -> str:
    """'ID TIENDA' -> ID_TIENDA, '#SUC' -> NUM_SUC, 'ACTIVA?' -> ACTIVA."""
    s = unicodedata.normalize("NFKD", str(nombre)).encode("ascii", "ignore").decode()
    s = s.replace("#", "NUM_")
    s = re.sub(r"[^0-9A-Za-z]+", "_", s).strip("_").upper() or "COL"
    return "C_" + s if s[0].isdigit() else s


def crear_vista(con, name: str, d: dict):
    """Crea la vista `name` sobre los parquets, con nombres de columna normalizados."""
    src = f"read_parquet('{d['path']}', union_by_name=true)"
    cols = con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()
    forzar = {c.upper() for c in CFG.get("forzar_texto", [])}
    usados, sel = {}, []
    for c in cols:
        orig = c[0]
        n = _norm(orig)
        usados[n] = usados.get(n, 0) + 1
        if usados[n] > 1:
            n = f"{n}_{usados[n]}"
        expr = '"' + orig.replace('"', '""') + '"'
        if n in forzar:
            expr = f"CAST({expr} AS VARCHAR)"
        sel.append(f'{expr} AS "{n}"')
    con.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT {', '.join(sel)} FROM {src}")


def crear_vistas_base(con):
    for name, d in CFG["datasets"].items():
        try:
            crear_vista(con, name, d)
        except Exception as e:
            raise RuntimeError(f"No pude leer '{name}' ({d['path']}): {e}") from e


def crear_vistas_diagnostico(con):
    vistas = ROOT / "vistas.sql"
    if vistas.exists() and CFG.get("views"):
        sql = vistas.read_text(encoding="utf-8").format(**CFG["cols"], **CFG["umbrales"])
        for stmt in sql.split(";"):
            lineas = [l.strip() for l in stmt.splitlines()]
            if any(l and not l.startswith("--") for l in lineas):
                con.execute(stmt)


def connect():
    con = duckdb.connect()
    crear_vistas_base(con)
    crear_vistas_diagnostico(con)
    return con


# ---------- contexto que ve el modelo ----------
def _list_tables(cur) -> str:
    rows = []
    for name, d in CFG["datasets"].items():
        n = cur.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        rango = ""
        if d.get("date_col"):
            lo, hi = cur.execute(
                f'SELECT min("{d["date_col"]}"), max("{d["date_col"]}") FROM {name}'
            ).fetchone()
            rango = f"{lo} -> {hi}"
        rows.append(f"- {name}: {d.get('description','')} | filas={n:,} | fechas={rango}")
    for name, desc in (CFG.get("views") or {}).items():
        rows.append(f"- {name} (vista de diagnóstico): {desc}")
    return "\n".join(rows)


def catalogo_texto(con) -> str:
    """Perfila las tablas (columnas, tipos, rangos, valores típicos). Es lo que el modelo sabe del esquema."""
    lines = ["# CATÁLOGO DE TABLAS (autogenerado al arrancar)\n"]
    for name, d in CFG["datasets"].items():
        lines.append(f"## Tabla `{name}`\n{d.get('description','')}\n")
        summ = con.execute(f"SUMMARIZE {name}").df()
        lines.append("| columna | tipo | min | max | únicos aprox. | % nulos |")
        lines.append("|---|---|---|---|---|---|")
        for _, r in summ.iterrows():
            lines.append(
                f"| {r['column_name']} | {r['column_type']} | {r['min']} | {r['max']} "
                f"| {r['approx_unique']} | {r['null_percentage']} |"
            )
        for _, r in summ.iterrows():  # valores típicos de columnas categóricas pequeñas
            if str(r["column_type"]).startswith("VARCHAR") and r["approx_unique"] <= 30:
                vals = con.execute(
                    f"SELECT DISTINCT {r['column_name']} FROM {name} WHERE {r['column_name']} IS NOT NULL LIMIT 30"
                ).fetchall()
                lines.append(f"\nValores de `{r['column_name']}`: " + ", ".join(str(v[0]) for v in vals))
        if CFG.get("incluir_muestras", True):
            lines.append("\nMuestra:\n")
            lines.append(con.execute(f"SELECT * FROM {name} LIMIT 3").df().to_markdown(index=False))
        lines.append("\n")
    for name, desc in (CFG.get("views") or {}).items():
        lines.append(f"## Vista `{name}`\n{desc}\n")
        lines.append(con.execute(f"DESCRIBE {name}").df()[["column_name", "column_type"]].to_markdown(index=False))
        lines.append("\n")
    return "\n".join(lines)


def build_system(con) -> str:
    """Instrucciones completas para el modelo: reglas + resumen de datos + catálogo + definiciones de negocio."""
    cur = con.cursor()
    partes = [
        RULES.replace("{glosario}", tema.glosario_para_modelo()),
        "RESUMEN DE DATOS (al arrancar la app)\n" + _list_tables(cur),
        catalogo_texto(con),
    ]
    p = ROOT / "negocio.md"
    if p.exists():
        partes.append(p.read_text(encoding="utf-8"))
    return "\n\n".join(partes)


# ---------- herramientas ----------
TOOLS = [
    {
        "name": "run_sql",
        "description": "Ejecuta UN SELECT (dialecto DuckDB) de solo lectura. Devuelve máx. filas configuradas.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "El SELECT a ejecutar"}},
            "required": ["query"],
        },
    },
    {
        "name": "show_visual",
        "description": (
            "Muestra al usuario un gráfico, una tabla o tarjetas KPI a partir de UN SELECT de solo lectura. "
            "Úsala cuando una visual comunique mejor que el texto. Para kind=kpi la consulta debe devolver una sola fila. "
            "Recibirás los datos para poder interpretarlos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["bar", "barh", "line", "area", "donut", "scatter", "table", "kpi"]},
                "sql": {"type": "string", "description": "SELECT que produce los datos, ya ordenado y agregado"},
                "title": {"type": "string", "description": "Título que dice la conclusión o el tema"},
                "x": {"type": "string", "description": "Columna del eje X o de las categorías"},
                "y": {"type": "array", "items": {"type": "string"}, "description": "Columna(s) de valores"},
                "color": {"type": "string", "description": "Columna opcional que separa series"},
                "format": {"type": "string", "enum": ["auto", "mxn", "unidades", "pct", "numero"]},
                "stacked": {"type": "boolean", "description": "Apilar barras"},
            },
            "required": ["kind", "sql", "title"],
        },
    },
]

MAX_VISUALES = 4


def _ejecutar(cur, query: str):
    """Valida y ejecuta. Devuelve (DataFrame, None) o (None, mensaje_de_error)."""
    try:
        stmts = cur.extract_statements(query)
        if len(stmts) != 1 or stmts[0].type != duckdb.StatementType.SELECT:
            return None, "Solo se permite un único SELECT."
        if BLOCK.search(query):
            return None, "Query no permitido (acceso a archivos/comandos)."
        timer = threading.Timer(CFG["query_timeout_s"], cur.interrupt)
        timer.start()
        try:
            limit = CFG["max_rows"]
            df = cur.execute(f"SELECT * FROM ({query.strip().rstrip(';')}) LIMIT {limit}").df()
        finally:
            timer.cancel()
        return df, None
    except Exception as e:  # el modelo se autocorrige con este mensaje
        return None, f"Error: {e}"


def _run_sql(cur, query: str) -> str:
    df, err = _ejecutar(cur, query)
    if err:
        return err
    if df.empty:
        return "0 filas."
    out = df.to_markdown(index=False)
    if len(df) == CFG["max_rows"]:
        out += f"\n(resultado truncado a {CFG['max_rows']} filas: agrega más en SQL)"
    return out


def _despachar(cur, nombre: str, args: dict, sqls: list, visuales: list) -> str:
    """Ejecuta una herramienta pedida por el modelo y devuelve el texto que el modelo verá."""
    if nombre == "show_visual":
        if len(visuales) >= MAX_VISUALES:
            return f"Límite de {MAX_VISUALES} visuales por respuesta. Resume el resto en texto."
        df, err = _ejecutar(cur, args.get("sql", ""))
        if err:
            return err
        if df.empty:
            return "La consulta no devolvió filas: no hay nada que mostrar."
        spec = {k: args.get(k) for k in ("kind", "title", "x", "y", "color", "format", "stacked")}
        visuales.append((spec, df))
        sqls.append(args["sql"])
        return f"Visual «{spec['title']}» mostrada al usuario ({len(df)} filas). Datos:\n" + df.head(30).to_markdown(index=False)
    if nombre == "run_sql":
        sqls.append(args.get("query", ""))
        return _run_sql(cur, args.get("query", ""))
    return f"Herramienta desconocida: {nombre}. Usa run_sql o show_visual."


def ask(client, cur, historial: list, pregunta: str, system: str):
    """Responde una pregunta. Devuelve (texto, sqls_ejecutados, visuales[(spec, DataFrame)]).

    historial: lista de {"role": "user"|"assistant", "content": texto} (solo texto, sin herramientas).
    Lanza llm.ErrorLLM con mensaje claro si la IA falla (cuota, conexión, clave...).
    """
    sqls, visuales = [], []

    def despachar(nombre, args):
        return _despachar(cur, nombre, args, sqls, visuales)

    texto = llm.conversar(
        client,
        system=system,
        historial=historial,
        pregunta=pregunta,
        tools=TOOLS,
        despachar=despachar,
        modelos=[CFG.get("modelo"), CFG.get("modelo_respaldo")],
        max_pasos=CFG.get("max_pasos", 6),
    )
    return texto, sqls, visuales
