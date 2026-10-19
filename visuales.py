"""Render de visuales (Plotly + tarjetas KPI) con la paleta azul de Casa Lumina y etiquetas en lenguaje de KAM."""
import html
import inspect
import re

import pandas as pd
import plotly.express as px
import streamlit as st

import tema

_DINERO = ("mxn", "valor", "venta", "ingreso", "revenue", "monto", "importe")
_PCT = ("pct", "porcentaje", "crecimiento", "participacion")


def _ancho() -> dict:
    """Streamlit nuevo usa width='stretch'; el viejo usa use_container_width."""
    p = inspect.signature(st.plotly_chart).parameters
    return {"width": "stretch"} if "width" in p else {"use_container_width": True}


def _col(df, nombre):
    """Nombre real de la columna (sin importar mayúsculas) o None."""
    if not nombre:
        return None
    for c in df.columns:
        if str(c).lower() == str(nombre).lower():
            return c
    return None


def _fmt_auto(nombre, fmt) -> str:
    if fmt and fmt != "auto":
        return fmt
    n = str(nombre).lower()
    if any(k in n for k in _PCT):
        return "pct"
    if any(k in n for k in _DINERO):
        return "mxn"
    return "numero"


def formato(v, fmt: str) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    try:
        v = float(v)
    except (TypeError, ValueError):
        return html.escape(str(v))
    if fmt == "mxn":
        return f"${v:,.0f}"
    if fmt == "pct":
        return f"{v:,.1f}%"
    if fmt == "unidades":
        return f"{v:,.0f}"
    return f"{v:,.0f}" if abs(v - round(v)) < 1e-9 else f"{v:,.2f}"


def tarjetas(df, fmt="auto", titulo=None):
    """Una fila = una tarjeta por columna."""
    fila = df.iloc[0]
    celdas = []
    for c, v in fila.items():
        etiqueta = html.escape(tema.encabezado(c))
        celdas.append(
            f'<div class="vs-kpi"><div class="vs-kpi-v">{formato(v, _fmt_auto(c, fmt)).replace("$", "&#36;")}</div>'
            f'<div class="vs-kpi-l">{etiqueta}</div></div>'
        )
    cab = f'<div class="vs-vis-t">{html.escape(str(titulo))}</div>' if titulo else ""
    st.markdown(f'{cab}<div class="vs-kpis">{"".join(celdas)}</div>', unsafe_allow_html=True)


def figura(spec: dict, df):
    """Devuelve una figura Plotly con la paleta de marca, o None si no se puede graficar."""
    kind = spec.get("kind")
    y = spec.get("y") or []
    if isinstance(y, str):
        y = [y]
    ys = [c for c in (_col(df, n) for n in y) if c is not None]
    x = _col(df, spec.get("x"))
    color = _col(df, spec.get("color"))
    if not ys:
        ys = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c]) and c != x][:1]
    if x is None:
        otras = [c for c in df.columns if c not in ys]
        x = otras[0] if otras else None
    if x is None or not ys:
        return None

    fmt = _fmt_auto(ys[0], spec.get("format"))
    multi = len(ys) > 1
    if multi:
        color = None  # con varias columnas de valor, el color lo da la serie
    cmap = tema.mapa_colores(df, x, color)  # colores por código interno (QUIEBRE, EN_TRANSITO...)
    if cmap:
        cmap = {tema.etiqueta(k): v for k, v in cmap.items()}  # y luego, por la etiqueta que ve el usuario
    df = tema.etiquetar_valores(df)
    if cmap and color is None and not multi and kind in ("bar", "barh", "donut"):
        color = x  # cada categoría con su color fijo
    extra = {"color_discrete_map": cmap} if cmap else {}
    stacked = "relative" if spec.get("stacked") else "group"
    yv = ys if multi else ys[0]

    if kind == "barh":
        fig = px.bar(df, x=yv, y=x, color=color, orientation="h", barmode=stacked, **extra)
        fig.update_yaxes(autorange="reversed")  # el primero (mayor) arriba
    elif kind == "bar":
        fig = px.bar(df, x=x, y=yv, color=color, barmode=stacked, **extra)
    elif kind == "line":
        fig = px.line(df, x=x, y=yv, color=color, markers=True, **extra)
    elif kind == "area":
        fig = px.area(df, x=x, y=yv, color=color, **extra)
    elif kind == "donut":
        fig = px.pie(df, names=x, values=ys[0], hole=0.55, color=color, **extra)
        fig.update_traces(textinfo="percent+label", marker=dict(line=dict(color="white", width=2)))
    elif kind == "scatter":
        fig = px.scatter(df, x=x, y=ys[0], color=color, **extra)
    else:
        return None

    fig.update_layout(
        font=dict(family=tema.FUENTE, color=tema.TEXTO, size=13),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        colorway=tema.COLORWAY,
        margin=dict(l=10, r=10, t=52, b=10),
        title=dict(text=str(spec.get("title") or ""), x=0, font=dict(size=16, color=tema.AZUL_OSCURO)),
        legend=dict(orientation="h", y=-0.2, title=None),
        showlegend=(color is not None and color != x) or multi,
    )
    fig.update_xaxes(title=None, gridcolor=tema.BORDE, zeroline=False)
    fig.update_yaxes(title=None, gridcolor=tema.BORDE, zeroline=False)
    if kind != "donut":
        eje = fig.update_xaxes if kind == "barh" else fig.update_yaxes
        if fmt == "mxn":
            eje(tickprefix="$", tickformat=",.0f")
        elif fmt == "pct":
            eje(ticksuffix="%")
    return fig


def mostrar(spec: dict, df, key: str):
    kind = spec.get("kind")
    titulo = spec.get("title")
    if df is None or df.empty:
        st.info("La consulta no devolvió filas.")
        return
    nombre = re.sub(r"[^a-z0-9]+", "_", str(titulo or "datos").lower()).strip("_") or "datos"
    legible = tema.encabezados(tema.etiquetar_valores(df))  # lo que ve el usuario en tablas y descargas
    csv = legible.to_csv(index=False).encode("utf-8-sig")

    if kind == "kpi":
        tarjetas(df, spec.get("format"), titulo)
        return
    if kind == "table":
        if titulo:
            st.markdown(f'<div class="vs-vis-t">{html.escape(str(titulo))}</div>', unsafe_allow_html=True)
        st.dataframe(legible, hide_index=True)
        st.download_button("Descargar CSV", csv, file_name=f"{nombre}.csv", mime="text/csv", key=f"{key}_csv")
        return

    fig = figura(spec, df)
    if fig is None:
        st.dataframe(legible, hide_index=True)
    else:
        st.plotly_chart(fig, key=f"{key}_fig", **_ancho())
    with st.expander("Ver datos"):
        st.dataframe(legible, hide_index=True)
        st.download_button("Descargar CSV", csv, file_name=f"{nombre}.csv", mime="text/csv", key=f"{key}_csv")
