# DEFINICIONES DE NEGOCIO (es lo que más mejora la calidad para darle un buen contexto a la llamada dentro del códgio)
#El objetivo es darle el mayor contexto, si el chatbot falla ocn alguna respuesta podemos volver y especificarla aquí

## Tablas y llaves
- `sellout`: una fila por DATE x ID_OUTLET x EAN **solo en días con venta** (un día sin fila = venta cero).
  `U` = unidades, `V` = valor en pesos mexicanos (MXN) sin IVA. `ID_RETAILER` = código de la cadena (HCOS, SAUR, MVAL, DNOR, CMER, BSOL).
  Hay un parquet por año.
- `inventarios`: una fila por DATE x ID_OUTLET x EAN.
  `INV_TIENDA` = inventario en tienda, `INV_TRANSITO` = unidades en tránsito (hacia la tienda),
  `INV_CEDIS` = unidades en CEDIS (centro de distribución de la cadena), `UNID_ORDENADAS` = unidades ordenadas (pedido abierto).
- `cat_tiendas`: llave `ID_OUTLET` (formato <código de cadena>_<número de tienda>).
  Columnas útiles: ID_RETAILER, RETAILER (nombre de la cadena), FORMATO, TIPO_FORMATO (HIPER, SUPER, EXPRESS, PROXIMIDAD, CLUB, DESCUENTO), NOMBRE, REGION, ESTADO, CIUDAD.
- `cat_eans`: llave `EAN`. Columnas útiles: BRAND (marca), CATEGORY (categoría), SEGMENTO, PRESENTACION, SHORT_DESCRIPTION, DESCRIPTION.
- Las cadenas y marcas de Casa Lumina son ficticias. Cadenas: Hiper Costa, Super Aurora, Mercados del Valle, Despensa del Norte, Club Meridiano, Bodegas Sol. Marcas: Brisa Viva (ambientadores), Cristal Plus (lavandería), Quita Todo (limpiadores), Adios Bichos (insecticidas), Brillo Claro (lavatrastes).

## Dos capas de datos
- **Tablas crudas** (`sellout`, `inventarios`): historia completa. Usar para ventas por mes o año y comparativos largos.
  Escribe la fecha como `"DATE"` (entre comillas dobles).
- **Vistas de diagnóstico** (`v_base`, `v_semanal`, `v_diag_sku_tienda`): solo los últimos días configurados.
  Usan `tienda`, `fecha`, `ean`. Usar para faltantes, inventario, tendencias y «qué está pasando».

## Joins
- `ID_OUTLET` (o `tienda` en las vistas) = `cat_tiendas.ID_OUTLET`. LEFT JOIN, relación 1:1.
- `EAN` (o `ean`) = `cat_eans.EAN`. LEFT JOIN, relación 1:1.
- Para cortar por cadena, formato, región o ciudad usar `cat_tiendas`. Por marca, categoría o segmento usar `cat_eans`.
- Si falta el catálogo, agrupar como 'SIN CATALOGO' y avisarlo. Nunca descartar esas filas.

## Medidas
- `V` (valor): pesos mexicanos sin IVA. Presentar como MXN.
- `INV_TIENDA` (inventario en tienda): fotografía del día.
- «Ventas» sin más contexto = valor `V`. Si piden «piezas» o «unidades», usar `U`.

## Métricas derivadas (ya vienen calculadas en `v_diag_sku_tienda`)
- `vel_28` = unidades por día en los últimos 28 días. `vel_7` = en los últimos 7.
- `dias_inv` = inventario actual / vel_28 (se le dice «días de cobertura» al usuario).Esto tambien se ocnoce como days on hand
- `tend_7v21` = últimos 7 días vs los 21 previos. `z_tend` = qué tan relevante es estadísticamente.
- `uit_hoy` (en tránsito), `uoo_hoy` (ordenadas), `uiw_hoy` (en CEDIS) al último día con inventario.
- `repo_en_camino` = hay unidades en tránsito o en pedido.
- `pipeline` = qué hay detrás de la tienda: EN_TRANSITO, PEDIDO_ABIERTO, STOCK_EN_CEDIS_SIN_ENVIO o SIN_PIPELINE.
- `dias_sin_venta`, `dias_cero_14`, `reposiciones_28`, `v28`, `v28_prev`, `crec_28v28`.
- Venta diaria en riesgo por falta de producto ≈ `vel_28 * v28 / u28` (valor por día que se deja de vender).

## Playbook de diagnóstico (columna `situacion`; entre paréntesis, cómo se le dice al usuario)
- **QUIEBRE** («Sin producto en tienda (quiebre)»): inventario en tienda en cero y venta en los últimos 28 días. Venta perdida probable. Leer `pipeline`:
  `EN_TRANSITO` o `PEDIDO_ABIERTO`: probablemente temporal, dar seguimiento.
  `STOCK_EN_CEDIS_SIN_ENVIO`: hay producto en CEDIS que no se está enviando a la tienda. Problema de distribución de la cadena: escalar con la cadena.
  `SIN_PIPELINE`: nadie lo está reponiendo (sin tránsito, sin pedido y sin stock en CEDIS). Prioridad máxima: revisar pedido y abasto.
- **RIESGO_QUIEBRE** («Por agotarse»): menos de N días de cobertura al ritmo actual. Si el `pipeline` es SIN_PIPELINE, pedir o reponer antes de que se rompa.
- **CAIDA_POR_QUIEBRE_RECIENTE** («Venta a la baja por falta de producto»): la venta cae y hubo 3 o más días en cero en los últimos 14. Consistente con venta perdida por falta de producto.
- **CAIDA_CON_INVENTARIO** («Venta a la baja con producto en tienda»): la venta cae y hay producto. No es abasto: sugiere demanda, precio, exhibición, promo de competencia o producto escondido. Revisar en campo.
- **POSIBLE_INV_FANTASMA** («Inventario que parece no estar en anaquel»): el sistema marca inventario pero no hay venta desde hace mucho más de lo normal para ese producto. Puede ser inventario inflado en sistema o producto fuera de anaquel. Verificar físicamente.
- **SIN_ROTACION** («Producto sin movimiento»): hay inventario y no se vendió nada en 56 días. Candidato a revisar surtido.
- **SOBREINVENTARIO** («Exceso de inventario»): más de N días de cobertura. Riesgo de capital inmovilizado. No reponer.
- **ACELERANDO** («Venta en aceleración»): la venta sube de forma relevante. Revisar que el inventario alcance.
- **BAJO_VOLUMEN** («Poca venta para opinar»): muy pocas unidades para hablar de tendencia. No inventar una.
- **INV_DESACTUALIZADO** («Inventario sin actualizar»): el inventario no se actualiza hace varios días. No concluir nada de abasto con esa fila.
- **ESTABLE** («Sin alertas»): sin señal relevante.

## Relaciones inventario-venta útiles
- Reposición implícita (`v_base.reposicion_implicita` > 0): días en que entró mercancía. Poca frecuencia de reposición con faltantes frecuentes sugiere problema de abasto y no de demanda.
- Correlación inventario-venta (`corr()` sobre `v_semanal`): alta correlación positiva suele indicar que donde hay más producto se vende más. Cuidado: puede ser causalidad inversa.
- Compara solo semanas completas (`dias_con_data` = 7).

## Reglas de interpretación
- Compara períodos equivalentes (mismos días del mes). Menciona siempre hasta qué fecha llega la data.
- Pondera por valor: prioriza lo que más dinero mueve.
- Cadenas: usar el nombre de `cat_tiendas.RETAILER` o el código `ID_RETAILER`, según cómo pregunten.

## Ejemplos (pregunta -> SQL). 

P: ¿Cómo vamos por cadena este mes vs el mes anterior (mismos días)?
```sql
WITH f AS (SELECT max("DATE") AS hoy FROM sellout)
SELECT s.ID_RETAILER AS cadena,
       sum(s.V) FILTER (WHERE s."DATE" >= date_trunc('month', f.hoy) AND s."DATE" <= f.hoy) AS v_act,
       sum(s.V) FILTER (WHERE s."DATE" >= date_trunc('month', f.hoy) - INTERVAL 1 MONTH
                          AND s."DATE" <= f.hoy - INTERVAL 1 MONTH) AS v_ant
FROM sellout s CROSS JOIN f
GROUP BY 1
ORDER BY v_act DESC
```

P: ¿Cuánto vendimos por marca y categoría en los últimos 28 días?
```sql
SELECT coalesce(p.BRAND, 'SIN CATALOGO') AS marca, coalesce(p.CATEGORY, 'SIN CATALOGO') AS categoria,
       sum(s.U) AS unidades, sum(s.V) AS valor
FROM sellout s
LEFT JOIN cat_eans p ON s.EAN = p.EAN
WHERE s."DATE" > (SELECT max("DATE") FROM sellout) - INTERVAL 28 DAY
GROUP BY 1, 2
ORDER BY valor DESC
```

P: ¿Dónde estamos perdiendo venta por falta de producto y cuánto dinero es, por cadena y por qué motivo?
```sql
SELECT t.RETAILER AS cadena, d.pipeline,
       count(*) AS series_en_quiebre,
       round(sum(d.vel_28 * d.v28 / nullif(d.u28, 0)), 0) AS venta_diaria_en_riesgo_mxn
FROM v_diag_sku_tienda d
LEFT JOIN cat_tiendas t ON d.tienda = t.ID_OUTLET
WHERE d.situacion = 'QUIEBRE'
GROUP BY 1, 2
ORDER BY venta_diaria_en_riesgo_mxn DESC
```

P: ¿Qué tiendas tienen inventario pero no venden?
```sql
SELECT d.tienda, t.NOMBRE, d.ean, p.SHORT_DESCRIPTION, d.inv_hoy, d.dias_sin_venta
FROM v_diag_sku_tienda d
LEFT JOIN cat_tiendas t ON d.tienda = t.ID_OUTLET
LEFT JOIN cat_eans p ON d.ean = p.EAN
WHERE d.situacion = 'POSIBLE_INV_FANTASMA'
ORDER BY d.inv_hoy DESC
LIMIT 30
```

P: ¿Qué está pasando por marca? (resumen de situaciones ponderado por valor)
```sql
SELECT coalesce(p.BRAND, 'SIN CATALOGO') AS marca, d.situacion,
       count(*) AS series, round(sum(d.v28), 0) AS valor_28d
FROM v_diag_sku_tienda d
LEFT JOIN cat_eans p ON d.ean = p.EAN
GROUP BY 1, 2
ORDER BY marca, valor_28d DESC
```

P: ¿Qué marcas crecen y cuáles caen? (mismo período del año anterior)
```sql
WITH f AS (SELECT max("DATE") AS hoy FROM sellout)
SELECT coalesce(p.BRAND, 'SIN CATALOGO') AS marca,
       sum(s.V) FILTER (WHERE s."DATE" >= date_trunc('year', f.hoy) AND s."DATE" <= f.hoy) AS valor_este_ano,
       sum(s.V) FILTER (WHERE s."DATE" >= date_trunc('year', f.hoy) - INTERVAL 1 YEAR
                          AND s."DATE" <= f.hoy - INTERVAL 1 YEAR) AS valor_ano_anterior
FROM sellout s CROSS JOIN f
LEFT JOIN cat_eans p ON s.EAN = p.EAN
GROUP BY 1
ORDER BY valor_este_ano DESC
```

P: ¿Los EANs que más venden dependen de tener más inventario? (correlación semanal)
```sql
SELECT ean, round(corr(inv_prom, unidades), 2) AS corr_inv_venta, count(*) AS observaciones
FROM v_semanal
WHERE dias_con_data = 7
GROUP BY 1
HAVING count(*) >= 30
ORDER BY corr_inv_venta DESC
LIMIT 20
```
