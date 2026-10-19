"""Genera datos 100% FICTICIOS de «Casa Lumina», una empresa de consumo masivo INVENTADA.
Este código la verdad es avaricia pero por si alguien quiere jugar un ratitot con la creación de datos sinteticos puede usarlo.

Nada de esto es real: ni la empresa, ni las cadenas, ni las marcas, ni las tiendas, ni las cifras.
Los códigos de barras (EAN) empiezan con 299, un rango que el estándar GS1 reserva para uso interno
y que no pertenece a ninguna empresa.

  data/sellout/sellout_2025.parquet, sellout_2026.parquet   (un parquet por año)
      DATE, ID_RETAILER, ID_OUTLET, EAN, U, V
  data/inventarios/inventarios_2026.parquet
      DATE, ID_RETAILER, ID_OUTLET, EAN, INV_TIENDA, INV_TRANSITO, INV_CEDIS, UNID_ORDENADAS
  data/catalogos/cat_tiendas.parquet   (llave: ID_OUTLET)
  data/catalogos/cat_eans.parquet      (llave: EAN)

Las series tienen escenarios sembrados (quiebres, caídas con inventario, inventario fantasma,
sobreinventario, aceleración...) para que el diagnóstico tenga algo que encontrar.
Es determinista (misma semilla = mismos datos). Uso: python generar_datos_sinteticos.py
"""
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
SEED = 7
INI_SELLOUT = date(2025, 1, 1)
INI_INV = date(2026, 1, 1)
FIN = date(2026, 10, 11)  # última fecha con data

# ---------------------------------------------------------------- dimensiones
# Cadenas inventadas. regiones=None significa que tiene tiendas en todo el país.
RETAILERS = [
    dict(id="HCOS", nombre="HIPER COSTA", n=55, regiones=None,
         formatos=[("HIPER COSTA", "HIPER"), ("HIPER COSTA EXPRESS", "EXPRESS")]),
    dict(id="SAUR", nombre="SUPER AURORA", n=50, regiones=None,
         formatos=[("SUPER AURORA", "SUPER"), ("AURORA EXPRESS", "EXPRESS")]),
    dict(id="MVAL", nombre="MERCADOS DEL VALLE", n=40, regiones=["CENTRO", "OCCIDENTE"],
         formatos=[("MERCADOS DEL VALLE", "SUPER"), ("MERCADITO DEL VALLE", "PROXIMIDAD")]),
    dict(id="DNOR", nombre="DESPENSA DEL NORTE", n=35, regiones=["NORTE"],
         formatos=[("DESPENSA DEL NORTE", "SUPER"), ("DESPENSA DEL NORTE MAXI", "HIPER")]),
    dict(id="CMER", nombre="CLUB MERIDIANO", n=25, regiones=["NORTE", "OCCIDENTE", "CENTRO"],
         formatos=[("CLUB MERIDIANO", "CLUB")]),
    dict(id="BSOL", nombre="BODEGAS SOL", n=45, regiones=None,
         formatos=[("BODEGAS SOL", "DESCUENTO"), ("BODEGAS SOL EXPRESS", "EXPRESS")]),
]

# tipo de formato -> (escala de venta, mínimo y máximo de productos que maneja la tienda)
TIPOS = {
    "HIPER": (1.4, 18, 34), "CLUB": (1.8, 16, 28), "SUPER": (1.0, 10, 22),
    "PROXIMIDAD": (0.6, 6, 12), "EXPRESS": (0.6, 6, 12), "DESCUENTO": (0.9, 8, 16),
}

GEO = [  # estado, ciudad, región
    ("HIDALGO", "PACHUCA", "CENTRO"), ("SAN LUIS POTOSI", "SAN LUIS POTOSI", "OCCIDENTE"),
    ("NUEVO LEON", "MONTERREY", "NORTE"), ("COAHUILA", "SALTILLO", "NORTE"),
    ("JALISCO", "GUADALAJARA", "OCCIDENTE"), ("GUANAJUATO", "LEON", "OCCIDENTE"),
    ("YUCATAN", "MERIDA", "SUR"), ("QUINTANA ROO", "CANCUN", "SUR"),
    ("VERACRUZ", "COATZACOALCOS", "SUR"), ("PUEBLA", "PUEBLA", "CENTRO"),
    ("MORELOS", "CUERNAVACA", "CENTRO"), ("SINALOA", "CULIACAN", "NORTE"),
]

# marca: (categoría, crecimiento anual de la demanda, [(segmento, abreviatura, variantes, presentaciones, precio_min, precio_max)])
MARCAS = {
    "BRISA VIVA": ("AMBIENTADORES", 0.05, [
        ("RECARGA AUTOMATICA", "RECARGA", ["LAVANDA", "CITRICOS", "BRISA MARINA", "FLORES BLANCAS"], ["250ML", "500ML"], 45, 95),
        ("ELECTRICO", "ELECTRICO", ["JAZMIN", "CAMPO VERDE", "VAINILLA"], ["1 PZA", "2 PZAS"], 95, 170),
        ("AEROSOL", "AEROSOL", ["FRESCURA", "NARANJA"], ["300ML", "400ML"], 40, 80),
    ]),
    "CRISTAL PLUS": ("LAVANDERIA", -0.15, [
        ("ANTISARRO POLVO", "ANTISARRO", ["ORIGINAL", "FRESCO", "SIN AROMA"], ["500G", "1KG"], 70, 140),
        ("TABLETAS", "TABLETAS", ["3 EN 1", "LIMON"], ["15 PZAS", "30 PZAS"], 85, 160),
    ]),
    "QUITA TODO": ("LIMPIADORES", 0.08, [
        ("LIMPIADOR BANO", "BANO", ["CAL Y SARRO", "ANTIMOHO", "CITRICO"], ["500ML", "750ML"], 40, 80),
        ("LIMPIADOR COCINA", "COCINA", ["DESENGRASANTE", "POWER", "LIMON"], ["500ML", "750ML"], 40, 85),
        ("MULTIUSOS", "MULTIUSOS", ["ORIGINAL"], ["500ML", "1L"], 35, 70),
    ]),
    "ADIOS BICHOS": ("INSECTICIDAS", 0.0, [
        ("AEROSOL", "AEROSOL", ["MATA TODO", "MOSCAS Y MOSQUITOS", "CUCARACHAS"], ["230ML", "360ML"], 55, 95),
        ("ELECTRICO", "ELECTRICO", ["LIQUIDO 45 NOCHES", "PLAQUITAS"], ["1 PZA", "2 PZAS"], 90, 150),
        ("CEBO HORMIGAS", "CEBO", ["GEL"], ["2 PZAS", "4 PZAS"], 45, 85),
    ]),
    "BRILLO CLARO": ("LAVATRASTES", 0.25, [
        ("LIQUIDO", "LIQUIDO", ["LIMON", "ANTIBACTERIAL", "MANZANA", "ALOE"], ["500ML", "900ML"], 30, 65),
        ("PASTA", "PASTA", ["CLASICA", "LIMON"], ["400G", "850G"], 35, 70),
    ]),
}


def digito_ean(doce: str) -> str:
    s = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(doce))
    return str((10 - s % 10) % 10)


def crear_catalogos(rng):
    # ---- productos (66 en total)
    prods = []
    n = 0
    for marca, (cat, crecimiento, segs) in MARCAS.items():
        for seg, abrev, variantes, presentaciones, pmin, pmax in segs:
            for var in variantes:
                base = float(rng.uniform(pmin, pmax))
                for i, pack in enumerate(presentaciones):
                    n += 1
                    doce = f"299{n:09d}"
                    ean = doce + digito_ean(doce)
                    precio = round(base * (1 + 0.7 * i) // 5 * 5 + 4.90, 2)  # termina en .90
                    prods.append(dict(
                        EAN=ean,
                        DESCRIPTION=f"{marca} {abrev} {var} {pack}",
                        SHORT_DESCRIPTION=f"{abrev} {var}",
                        BRAND=marca, CATEGORY=cat, SEGMENTO=seg, PRESENTACION=pack,
                        _precio=precio, _crecimiento=crecimiento,
                    ))
    prods = pd.DataFrame(prods)

    # ---- tiendas (250 en total)
    tiendas = []
    for r in RETAILERS:
        geos = [g for g in GEO if r["regiones"] is None or g[2] in r["regiones"]]
        nums = rng.choice(np.arange(1, 1000), size=r["n"], replace=False)
        for num in nums:
            formato, tipo = r["formatos"][int(rng.integers(0, len(r["formatos"])))]
            estado, ciudad, region = geos[int(rng.integers(0, len(geos)))]
            tiendas.append({
                "ID_OUTLET": f"{r['id']}_{int(num):04d}", "ID_RETAILER": r["id"], "RETAILER": r["nombre"],
                "FORMATO": formato, "TIPO_FORMATO": tipo,
                "NOMBRE": f"{formato} {ciudad}, SUC. {int(num)}",
                "REGION": region, "ESTADO": estado, "CIUDAD": ciudad,
            })
    return prods, pd.DataFrame(tiendas)


# ---------------------------------------------------------------- simulación
ESC = ["normal", "quiebre", "caida_inv", "fantasma", "sobreinv", "riesgo", "acelera", "caida_quiebre"]
PROB = [0.63, 0.06, 0.06, 0.04, 0.06, 0.06, 0.05, 0.04]


def simular(seed=SEED):
    rng = np.random.default_rng(seed)
    prods, tiendas = crear_catalogos(rng)

    # series tienda x EAN (cada tienda maneja un subconjunto del catálogo, según su formato)
    ser_t, ser_e, ser_escala = [], [], []
    for _, t in tiendas.iterrows():
        escala, kmin, kmax = TIPOS[t["TIPO_FORMATO"]]
        k = int(rng.integers(kmin, kmax + 1))
        for j in rng.choice(len(prods), size=k, replace=False):
            ser_t.append(t["ID_OUTLET"])
            ser_e.append(j)
            ser_escala.append(escala)
    S = len(ser_t)
    ser_t = np.array(ser_t)
    ser_escala = np.array(ser_escala)
    ser_ret = tiendas.set_index("ID_OUTLET").loc[ser_t, "ID_RETAILER"].to_numpy()
    ser_ean = prods["EAN"].to_numpy()[ser_e]
    ser_precio = prods["_precio"].to_numpy()[ser_e]
    ser_crec = prods["_crecimiento"].to_numpy()[ser_e]

    dias = pd.date_range(INI_SELLOUT, FIN)
    T = len(dias)
    t_inv0 = int((pd.Timestamp(INI_INV) - pd.Timestamp(INI_SELLOUT)).days)

    lam = np.clip(np.exp(rng.normal(-0.2, 0.8, S)) * ser_escala, 0.08, 8.0)
    esc = rng.choice(ESC, size=S, p=PROB)
    lead = rng.integers(2, 5, S)

    # política de reposición
    rop = np.ceil(lam * 5).astype(int)
    target = np.maximum(4, np.ceil(lam * 28)).astype(int)
    m = esc == "sobreinv"
    rop[m], target[m] = np.ceil(lam[m] * 60).astype(int), np.ceil(lam[m] * 120).astype(int)
    m = esc == "riesgo"
    rop[m], target[m] = np.floor(lam[m] * 2).astype(int), np.maximum(2, np.ceil(lam[m] * 6)).astype(int)

    # ventanas de bloqueo de reposición y choques de demanda (relativas al final de la serie)
    b_ini, b_fin = np.full(S, T + 1), np.full(S, T + 1)
    s_ini, s_mult = np.full(S, T + 1), np.ones(S)
    m = esc == "quiebre"
    b_ini[m] = T - rng.integers(18, 27, m.sum())
    m = esc == "caida_quiebre"
    b_ini[m], b_fin[m] = T - 20, T - 9
    m = esc == "fantasma"
    f = T - rng.integers(16, 31, m.sum())
    b_ini[m], s_ini[m], s_mult[m] = f, f, 0.0
    m = esc == "caida_inv"
    s_ini[m], s_mult[m] = T - 8, 0.35
    m = esc == "acelera"
    s_ini[m], s_mult[m] = T - 8, 2.2

    inv = target.copy()
    pend_q = np.zeros(S, dtype=int)
    pend_eta = np.zeros(S, dtype=int)
    dow = np.array([1.0, 1.0, 1.0, 1.0, 1.15, 1.35, 1.25])

    umat = np.zeros((T, S), dtype=np.int32)
    n_inv = T - t_inv0
    uoh = np.zeros((n_inv, S), dtype=np.int32)
    uit = np.zeros((n_inv, S), dtype=np.int32)
    uoo = np.zeros((n_inv, S), dtype=np.int32)
    uiw = np.zeros((n_inv, S), dtype=np.int32)

    for t in range(T):
        bloq = (t >= b_ini) & (t < b_fin)
        sem = (esc == "fantasma") & (t == b_ini) & (inv == 0)  # el fantasma congela inventario > 0
        inv[sem] = np.maximum(1, np.ceil(lam[sem] * 5)).astype(int)
        llega = (pend_q > 0) & (pend_eta <= t) & ~bloq
        inv[llega] += pend_q[llega]
        pend_q[llega] = 0
        mult = np.where(t >= s_ini, s_mult, 1.0)
        tendencia = (1.0 + ser_crec) ** (t / 365.0)  # cada marca crece o cae a su propio ritmo
        dem = rng.poisson(lam * dow[dias[t].weekday()] * mult * tendencia)
        u = np.minimum(dem, inv)
        inv = inv - u
        umat[t] = u
        pedir = (pend_q == 0) & (inv <= rop) & ~bloq
        pend_q[pedir] = np.maximum(target[pedir] - inv[pedir], 1)
        pend_eta[pedir] = t + lead[pedir]
        if t >= t_inv0:
            k = t - t_inv0
            falta = pend_eta - t
            uoh[k] = inv
            uoo[k] = np.where((pend_q > 0) & (falta > 1), pend_q, 0)
            uit[k] = np.where((pend_q > 0) & (falta <= 1), pend_q, 0)
            uiw[k] = np.where(rng.random(S) < 0.15, rng.integers(1, 12, S), 0)

    # ---- sell out: solo filas con venta (un día sin fila = venta cero)
    ti, si = np.nonzero(umat)
    unidades = umat[ti, si].astype(int)
    promo = np.where(rng.random(len(ti)) < 0.10, rng.uniform(0.85, 0.95, len(ti)), 1.0)
    sell = pd.DataFrame({
        "DATE": dias[ti], "ID_RETAILER": ser_ret[si], "ID_OUTLET": ser_t[si],
        "EAN": ser_ean[si], "U": unidades,
        "V": np.round(unidades * ser_precio[si] * promo, 2),
    })

    # ---- inventarios: una fila por tienda x EAN x día
    kk, si2 = np.meshgrid(np.arange(n_inv), np.arange(S), indexing="ij")
    kk, si2 = kk.ravel(), si2.ravel()
    inv_df = pd.DataFrame({
        "DATE": dias[t_inv0 + kk], "ID_RETAILER": ser_ret[si2], "ID_OUTLET": ser_t[si2],
        "EAN": ser_ean[si2],
        "INV_TIENDA": uoh[kk, si2], "INV_TRANSITO": uit[kk, si2],
        "INV_CEDIS": uiw[kk, si2], "UNID_ORDENADAS": uoo[kk, si2],
    })

    # catálogos: se omiten 1 EAN y 2 tiendas A PROPÓSITO (para probar el chequeo de cobertura y 'SIN CATALOGO')
    cat_e = prods.drop(columns=["_precio", "_crecimiento"]).iloc[:-1]
    cat_t = tiendas.iloc[:-2]
    return dict(sell=sell, inv=inv_df, cat_t=cat_t, cat_e=cat_e, esc=pd.DataFrame(
        {"ID_OUTLET": ser_t, "EAN": ser_ean, "escenario": esc}))


def escribir(d):
    import duckdb

    con = duckdb.connect()
    for sub in ("sellout", "inventarios", "catalogos"):
        (ROOT / "data" / sub).mkdir(parents=True, exist_ok=True)
        for f in (ROOT / "data" / sub).glob("*.parquet"):
            f.unlink()

    con.register("sell", d["sell"])
    for y in sorted(d["sell"]["DATE"].dt.year.unique()):
        out = (ROOT / "data" / "sellout" / f"sellout_{y}.parquet").as_posix()
        con.execute(f"""COPY (
            SELECT CAST("DATE" AS DATE) AS "DATE", ID_RETAILER, ID_OUTLET, CAST(EAN AS VARCHAR) AS EAN,
                   CAST(U AS BIGINT) AS U, V
            FROM sell WHERE year("DATE") = {int(y)} ORDER BY "DATE", ID_OUTLET, EAN
        ) TO '{out}' (FORMAT PARQUET)""")

    con.register("inv", d["inv"])
    out = (ROOT / "data" / "inventarios" / "inventarios_2026.parquet").as_posix()
    con.execute(f"""COPY (
        SELECT CAST("DATE" AS DATE) AS "DATE", ID_RETAILER, ID_OUTLET, CAST(EAN AS VARCHAR) AS EAN,
               CAST(INV_TIENDA AS BIGINT) AS INV_TIENDA, CAST(INV_TRANSITO AS BIGINT) AS INV_TRANSITO,
               CAST(INV_CEDIS AS BIGINT) AS INV_CEDIS, CAST(UNID_ORDENADAS AS BIGINT) AS UNID_ORDENADAS
        FROM inv ORDER BY "DATE", ID_OUTLET, EAN
    ) TO '{out}' (FORMAT PARQUET)""")

    for nombre, key in (("cat_t", "cat_tiendas"), ("cat_e", "cat_eans")):
        con.register(nombre, d[nombre])
        out = (ROOT / "data" / "catalogos" / f"{key}.parquet").as_posix()
        con.execute(f"COPY (SELECT * FROM {nombre}) TO '{out}' (FORMAT PARQUET)")


if __name__ == "__main__":
    d = simular()
    escribir(d)
    print("Datos ficticios de Casa Lumina generados en data/")
    print(f"  sellout:     {len(d['sell']):>9,} filas  ({d['sell']['DATE'].min().date()} -> {d['sell']['DATE'].max().date()})")
    print(f"  inventarios: {len(d['inv']):>9,} filas  ({d['inv']['DATE'].min().date()} -> {d['inv']['DATE'].max().date()})")
    print(f"  cat_tiendas: {len(d['cat_t']):>9,} tiendas | cat_eans: {len(d['cat_e']):>4,} productos")
    print("Escenarios sembrados (tienda x EAN):")
    print(d["esc"]["escenario"].value_counts().to_string())
