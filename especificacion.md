# Especificación · Casa Lumina · Sell Out & Inventarios

> Una buena especificación es la que otro asistente de IA podría construir sin hacer preguntas. De ella sale la ficha del hito de la semana 2.
> Casa Lumina es una empresa **ficticia** de consumo masivo. Todos los datos son inventados.

## 1. Problema y usuario

- **Quién tiene el problema:** el KAM (Key Account Manager) o analista comercial de una empresa de consumo masivo que vende a través de cadenas de autoservicio (en este caso, Casa Lumina y sus seis cadenas clientes).
- **Cómo lo resuelve hoy:** le pide un reporte de ventas e inventario al equipo de BI, o baja archivos de cada cadena y los cruza a mano en Excel. Cada pregunta nueva es un pedido nuevo.
- **Qué le molesta de cómo lo hace hoy:**
  - Espera horas o días, y cuando llega el reporte el faltante de producto ya pasó.
  - Ventas e inventario viven en lugares separados, así que le cuesta ver que una caída de venta puede deberse a producto atorado en el CEDIS de la cadena.
  - No sabe si puede confiar en el número, porque no ve cómo se calculó.
- **Qué parte resuelve la IA:** traducir una pregunta escrita en español a una consulta correcta, cruzar ventas con inventario y explicar el resultado con hipótesis prudentes y acciones concretas.
- **Qué parte se queda fuera:**
  - Calcular. Los números los calcula siempre una consulta SQL (DuckDB) sobre los datos; la IA no hace cuentas ni inventa cifras.
  - Las causas que los datos no traen (precio, promociones, exhibición, competencia). La app lo dice y sugiere qué revisar en campo.
  - Decidir y ejecutar la acción en campo.
- **Qué parte resuelve una hoja de cálculo (o un tablero fijo):** lo que ya se sabe que se va a preguntar. Por eso el **Tablero** funciona sin IA.

## 2. Qué hace el producto

1. **Preguntar en español sobre ventas e inventario.** La app responde en lenguaje de negocio: primero el hallazgo, luego las cifras de apoyo, las posibles causas y de 1 a 3 acciones. Quien quiera auditar abre «Ver SQL». La barra lateral trae preguntas de ejemplo.
2. **Pedir gráficos y tarjetas de resumen.** Si el usuario escribe «gráfico de venta semanal por cadena» o «un tablero de salud de inventario», la app dibuja el resultado y permite descargar los datos.
3. **Tablero de diagnóstico, sin IA.** Muestra qué productos están sin existencia en tienda, cuáles están por agotarse, cuáles tienen inventario dudoso y cuáles exceso, con filtro por cadena. Funciona siempre, incluso si se acaba la cuota de la IA o falta la clave.

## 3. Entradas y salidas

| El usuario da… | La app devuelve… | Ejemplo |
|---|---|---|
| Una pregunta en español | Hallazgo principal, cifras en MXN, hasta qué fecha llegan los datos, posibles causas, qué no se puede saber y 1 a 3 acciones. «Ver SQL» muestra la consulta. | «¿Dónde estoy perdiendo venta por falta de producto en Hiper Costa?» |
| Una petición de gráfico o tablero | Gráfico (líneas, barras, dona) o tarjetas de resumen, con descarga de los datos | «Gráfico de venta semanal por cadena» |
| Abrir el Tablero y, si quiere, elegir cadenas | Resumen, salud del inventario, ventas semanales y dónde actuar, sin usar IA | Filtrar por Club Meridiano |
| Clic en una pregunta rápida | La misma respuesta que si la hubiera escrito | «¿Qué marcas crecen y cuáles caen?» |

## 4. La pieza de IA

- **Opción elegida:** API de Gemini (capa gratuita) con herramientas (*function calling*). El modelo es una constante en `config.yaml` (`modelo`), con un modelo de respaldo para cuando el principal se queda sin cuota.
- **Por qué:**
  - La tarea es traducir lenguaje natural a consultas sobre datos **tabulares** y explicar el resultado. Un LLM por API lo hace bien y cuesta cero en la capa gratuita.
  - Un modelo pequeño de Hugging Face escribe SQL con menos fiabilidad y es más lento en un Space gratuito.
  - Un RAG busca fragmentos de documentos; aquí los números hay que **calcularlos**, no recuperarlos, así que no encaja.
  - La IA solo escribe la consulta y explica; DuckDB ejecuta. Así las cifras son verificables («Ver SQL»).
- **Instrucciones para el modelo (system prompt):** viven en `agent.py` (`RULES`) y se completan con el glosario de lenguaje de KAM, un resumen de los datos y `negocio.md`. Lo esencial:
  - Eres el asistente de sell out e inventarios de Casa Lumina; hablas con KAMs que no saben SQL, en español, directo y claro.
  - Nunca inventes números: todo sale de una consulta. Si falla, corrígela y reintenta.
  - Menciona siempre hasta qué fecha llegan los datos.
  - Nunca muestres SQL, nombres de columnas ni códigos internos; usa las etiquetas del glosario.
  - No afirmes causalidad («es consistente con…», «sugiere…»); di qué no se puede saber con estos datos.
  - Si la pregunta no es de ventas o inventario, di amablemente que no puedes ayudar y ofrece dos preguntas que sí.
  - Cierra con el insight principal y de 1 a 3 acciones.
- **Seguridad de las consultas:** un solo `SELECT`, sin leer archivos ni ejecutar comandos, con tope de 200 filas y 30 segundos.

## 5. Flujo del usuario

1. Entra a la app y ve «Pregúntale a tus datos», hasta qué fecha llegan los datos y que son datos ficticios.
2. Escribe una pregunta, o hace clic en una pregunta rápida, o abre el Tablero.
3. Recibe la respuesta con gráficos si ayudan, una lectura en lenguaje de negocio y acciones. Puede abrir «Ver SQL» para auditar o descargar los datos.
4. Si la IA no está disponible (cuota, conexión), ve un mensaje claro y puede seguir con el Tablero.

## 6. Restricciones

- Coste cero: capa gratuita de la API de Gemini y despliegue gratuito (ruta A, Streamlit Community Cloud).
- La clave de la API va en secretos (`st.secrets`), nunca en el código ni en el repositorio.
- Sin datos personales reales ni datos reales de ninguna empresa: todo es ficticio (empresa, cadenas, marcas, tiendas, códigos de barras y cifras).
- Lenguaje sencillo, para alguien sin conocimientos técnicos: sin códigos internos ni jerga de datos en la interfaz ni en las respuestas.
- La app funciona aunque falte la clave o se acabe la cuota (el Tablero no usa IA).
- Tope de 12 preguntas por sesión y 150 por día para toda la app, para cuidar la cuota gratuita.
- Python 3.12 y las dependencias de `requirements.txt`.

## 7. Criterios de aceptación

La app está bien si:

| Entrada | Resultado esperado |
|---|---|
| «¿Dónde estoy perdiendo venta por falta de producto?» | Responde en lenguaje de KAM con cifras en MXN, la fecha de corte de los datos, qué cadenas o tiendas pesan más, el motivo (viene en camino, hay en CEDIS pero no llega, nadie lo repone) y de 1 a 3 acciones. No muestra códigos como `QUIEBRE` ni `pipeline`. «Ver SQL» muestra la consulta. |
| «Gráfico de venta semanal por cadena» | Dibuja un gráfico de líneas con las seis cadenas y permite descargar los datos. |
| «¿Cómo vamos este mes contra el mes anterior?» | Compara períodos equivalentes (mismos días) y lo avisa. |
| Abrir el Tablero | Carga resumen, gráficos y tabla sin usar IA; al elegir una cadena, las cifras cambian. |
| Una pregunta fuera de tema («dame una receta de tacos») | Dice amablemente que no puede ayudar con eso y ofrece dos preguntas válidas. |
| Una pregunta que los datos no pueden contestar («¿cuánto vendió la competencia?») | Dice que los datos no lo traen y qué revisar en campo; no inventa. |
| Una tienda o producto fuera del catálogo | Aparece como «SIN CATALOGO» y la respuesta lo menciona. |
| Una orden peligrosa («borra todas las tablas») | No se ejecuta nada que no sea un `SELECT`; la app lo explica con sencillez. |
| Se acaba la cuota de la IA | Mensaje claro («llegó a su límite por ahora…») y el Tablero sigue disponible; nunca se muestra un error técnico. |
| No hay conexión con el servicio de IA | Mensaje claro de conexión y el Tablero sigue disponible. |
| Falta la clave de Gemini | El chat se muestra desactivado con un aviso; el Tablero funciona. |
| El visitante llega a 12 preguntas | Mensaje que explica el límite y sugiere el Tablero. |

## 8. Fuera de alcance (por ahora)

- Subir datos propios o conectar fuentes reales.
- Cuentas de usuario y conversaciones guardadas entre sesiones.
- Alertas por correo o WhatsApp.
- Pronóstico de ventas y metas por tienda.
- Cualquier dato real de una empresa.

## 9. Despliegue

- **Ruta:** A (Streamlit Community Cloud). Archivo principal: `app.py`.
- **Equipo:** no aplica (trabajo individual).
