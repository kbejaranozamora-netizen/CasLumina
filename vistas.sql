-- Vistas de diagnóstico. Los marcadores entre llaves se llenan desde config.yaml (cols y umbrales).
-- No uses punto y coma dentro de comentarios: el cargador separa por punto y coma.

-- v_base: sell out + inventario al grano tienda x fecha x EAN, solo los últimos ventana_dias días.
-- inv_unidades = inventario en tienda, uit = en tránsito, uiw = en CEDIS, uoo = ordenadas.
-- Cada lado se suma antes del join, para que filas repetidas (ej. por membresía) no multipliquen el resultado.
-- reposicion_implicita = inv_hoy - inv_ayer + ventas_hoy.
-- Positivo = entró mercancía. Negativo = merma, ajuste o dato inconsistente.
CREATE OR REPLACE VIEW v_base AS
WITH lim AS (
  SELECT greatest(
           (SELECT max("{fecha}") FROM sellout),
           (SELECT max("{fecha}") FROM inventarios)
         ) - INTERVAL {ventana_dias} DAY AS desde
),
s AS (
  SELECT "{tienda}" AS tienda, "{fecha}" AS fecha, "{cod}" AS ean,
         sum("{unidades}") AS unidades, sum("{valor}") AS valor
  FROM sellout, lim
  WHERE "{fecha}" >= lim.desde
  GROUP BY 1, 2, 3
),
i AS (
  SELECT "{tienda}" AS tienda, "{fecha}" AS fecha, "{cod}" AS ean,
         sum("{inv}") AS inv_unidades,
         sum("{inv_transito}") AS uit,
         sum("{inv_bodega}") AS uiw,
         sum("{inv_pedido}") AS uoo
  FROM inventarios, lim
  WHERE "{fecha}" >= lim.desde
  GROUP BY 1, 2, 3
),
b AS (
  SELECT
    coalesce(i.tienda, s.tienda) AS tienda,
    coalesce(i.fecha, s.fecha) AS fecha,
    coalesce(i.ean, s.ean) AS ean,
    coalesce(s.unidades, 0) AS unidades,
    coalesce(s.valor, 0) AS valor,
    i.inv_unidades, i.uit, i.uiw, i.uoo
  FROM i
  FULL OUTER JOIN s ON i.tienda = s.tienda AND i.fecha = s.fecha AND i.ean = s.ean
)
SELECT *,
  inv_unidades - lag(inv_unidades) OVER w + unidades AS reposicion_implicita
FROM b
WINDOW w AS (PARTITION BY tienda, ean ORDER BY fecha);

-- v_semanal: tendencia semanal por tienda x EAN. Comparar solo semanas con dias_con_data = 7.
CREATE OR REPLACE VIEW v_semanal AS
SELECT
  tienda, ean,
  date_trunc('week', fecha) AS semana,
  sum(unidades) AS unidades,
  sum(valor) AS valor,
  avg(inv_unidades) AS inv_prom,
  count(*) FILTER (WHERE inv_unidades <= 0) AS dias_inv_cero,
  count(DISTINCT fecha) AS dias_con_data
FROM v_base
GROUP BY 1, 2, 3;

-- v_diag_sku_tienda: foto a la última fecha con data, una fila por tienda x EAN.
-- situacion clasifica la relación inventario-venta.
-- pipeline indica qué hay detrás de la tienda: EN_TRANSITO, PEDIDO_ABIERTO, STOCK_EN_CEDIS_SIN_ENVIO o SIN_PIPELINE.
-- tend_7v21 compara los últimos 7 días contra los 21 previos (ventanas independientes).
-- Las tendencias solo se evalúan con volumen suficiente (min_unid_tend en 28 días) y si la desviación es
-- estadísticamente relevante (z_tend, tipo Poisson, mínimo z_tend_min): una semana +/-40% con 20 unidades es ruido normal.
-- Inventario fantasma exige un hueco de ventas mucho mayor al intervalo normal entre ventas de ese producto.
CREATE OR REPLACE VIEW v_diag_sku_tienda AS
WITH h AS (SELECT max(fecha) AS hoy FROM v_base),
m AS (
  SELECT
    b.tienda, b.ean,
    sum(unidades) FILTER (WHERE fecha > hoy - INTERVAL 7 DAY) AS u7,
    sum(unidades) FILTER (WHERE fecha > hoy - INTERVAL 28 DAY) AS u28,
    sum(unidades) FILTER (WHERE fecha <= hoy - INTERVAL 28 DAY AND fecha > hoy - INTERVAL 56 DAY) AS u28_prev,
    sum(valor) FILTER (WHERE fecha > hoy - INTERVAL 28 DAY) AS v28,
    sum(valor) FILTER (WHERE fecha <= hoy - INTERVAL 28 DAY AND fecha > hoy - INTERVAL 56 DAY) AS v28_prev,
    arg_max(inv_unidades, fecha) FILTER (WHERE inv_unidades IS NOT NULL) AS inv_hoy,
    arg_max(coalesce(uit, 0), fecha) FILTER (WHERE inv_unidades IS NOT NULL) AS uit_hoy,
    arg_max(coalesce(uoo, 0), fecha) FILTER (WHERE inv_unidades IS NOT NULL) AS uoo_hoy,
    arg_max(coalesce(uiw, 0), fecha) FILTER (WHERE inv_unidades IS NOT NULL) AS uiw_hoy,
    max(fecha) FILTER (WHERE inv_unidades IS NOT NULL) AS inv_fecha,
    avg(inv_unidades) FILTER (WHERE fecha > hoy - INTERVAL 28 DAY) AS inv_prom_28,
    count(*) FILTER (WHERE fecha > hoy - INTERVAL 14 DAY AND inv_unidades <= 0) AS dias_cero_14,
    max(fecha) FILTER (WHERE unidades > 0) AS ult_venta,
    count(*) FILTER (WHERE unidades > 0) AS dias_venta_56,
    count(*) FILTER (WHERE fecha > hoy - INTERVAL 28 DAY AND reposicion_implicita > 0) AS reposiciones_28
  FROM v_base b, h
  WHERE fecha > hoy - INTERVAL 56 DAY
  GROUP BY 1, 2
),
k AS (
  SELECT
    m.*, h.hoy,
    coalesce(u28, 0) / 28.0 AS vel_28,
    coalesce(u7, 0) / 7.0 AS vel_7,
    CASE WHEN coalesce(u28_prev, 0) > 0 THEN u28 * 1.0 / u28_prev - 1 END AS crec_28v28,
    CASE WHEN coalesce(u28, 0) - coalesce(u7, 0) > 0 THEN (coalesce(u7, 0) / 7.0) / ((u28 - coalesce(u7, 0)) / 21.0) - 1 END AS tend_7v21,
    CASE WHEN coalesce(u28, 0) - coalesce(u7, 0) > 0 THEN (coalesce(u7, 0) - (u28 - coalesce(u7, 0)) / 3.0) / sqrt((u28 - coalesce(u7, 0)) / 3.0) END AS z_tend,
    CASE WHEN coalesce(u28, 0) > 0 THEN inv_hoy / (u28 / 28.0) END AS dias_inv,
    date_diff('day', ult_venta, h.hoy) AS dias_sin_venta,
    (coalesce(uit_hoy, 0) + coalesce(uoo_hoy, 0)) > 0 AS repo_en_camino
  FROM m, h
)
SELECT
  k.*,
  CASE
    WHEN inv_fecha IS NULL OR inv_fecha < hoy - INTERVAL {dias_desact} DAY THEN 'INV_DESACTUALIZADO'
    WHEN coalesce(inv_hoy, 0) <= 0 AND coalesce(u28, 0) > 0 THEN 'QUIEBRE'
    WHEN coalesce(u28, 0) > 0 AND dias_inv < {dias_riesgo} THEN 'RIESGO_QUIEBRE'
    WHEN coalesce(inv_hoy, 0) > 0
         AND dias_sin_venta >= greatest({dias_fantasma}, 4 * 56.0 / nullif(dias_venta_56, 0)) THEN 'POSIBLE_INV_FANTASMA'
    WHEN coalesce(inv_hoy, 0) > 0 AND coalesce(u28, 0) = 0 THEN 'SIN_ROTACION'
    WHEN dias_inv > {dias_sobre} THEN 'SOBREINVENTARIO'
    WHEN coalesce(u28, 0) < {min_unid_tend} THEN 'BAJO_VOLUMEN'
    WHEN tend_7v21 < -{umbral_caida} AND z_tend <= -{z_tend_min} AND dias_cero_14 >= 3 THEN 'CAIDA_POR_QUIEBRE_RECIENTE'
    WHEN tend_7v21 < -{umbral_caida} AND z_tend <= -{z_tend_min} THEN 'CAIDA_CON_INVENTARIO'
    WHEN tend_7v21 > {umbral_caida} AND z_tend >= {z_tend_min} THEN 'ACELERANDO'
    ELSE 'ESTABLE'
  END AS situacion,
  CASE
    WHEN coalesce(uit_hoy, 0) > 0 THEN 'EN_TRANSITO'
    WHEN coalesce(uoo_hoy, 0) > 0 THEN 'PEDIDO_ABIERTO'
    WHEN coalesce(uiw_hoy, 0) > 0 THEN 'STOCK_EN_CEDIS_SIN_ENVIO'
    ELSE 'SIN_PIPELINE'
  END AS pipeline
FROM k;
