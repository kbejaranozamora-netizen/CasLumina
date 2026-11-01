# Casa Lumina · Sell Out & Inventarios

**Enlace a la app:** https://caslumina-mkpumudqyjkxcvkoszjr5z.streamlit.app/
**Autor/a:** Kathia Bejarano Zamora

> Todos los datos de esta app son **ficticios**: la empresa (Casa Lumina), las cadenas, las marhttps://github.com/kbejaranozamora-netizen/CasLumina/blob/main/README.mdcas, las tiendas, los códigos de barras y las cifras están inventados.

## Pitch

1. Los equipos comerciales de consumo masivo no ven a tiempo dónde les falta producto en tienda, y cada vez que quieren saberlo dependen de que alguien de BI les prepare un reporte.
2. Esta app deja preguntar en español por ventas e inventario, responde con cifras, gráficos y acciones, y trae un Tablero de diagnóstico que funciona sin IA.
3. La IA (Gemini) traduce una pregunta nueva a una consulta correcta, cruza ventas con inventario y explica el resultado con prudencia; los números los calcula siempre una consulta SQL (DuckDB), así que la IA no puede inventar cifras y cada una se puede auditar con «Ver SQL».
4. En la prueba descubrí tres cosas que no esperaba: Gemini a veces responde «saturado» (503), así que añadí reintentos y una cadena de cuatro modelos; a veces escribía códigos internos como `SIN_PIPELINE` en vez de lenguaje de KAM, así que la app ahora los traduce sola; y subir los archivos por separado rompió la app una vez, así que ahora los subo juntos.
5. Lo siguiente sería sumar una tabla de ejecución en tienda (exhibición, ubicación y precio en anaquel) para cruzarla con ventas e inventario y detectar oportunidades de ejecución: hoy, cuando la venta cae aunque hay producto, la app solo puede decir «se recomienda una revisión física en tienda», como hizo en mi prueba de «dónde pierdo venta», porque sus datos no traen exhibición ni ubicaciones.

## El problema

El KAM o analista comercial de una empresa de consumo masivo vende a través de cadenas de autoservicio. Hoy, para saber dónde pierde venta por falta de producto o cómo va una cadena contra el mes anterior, le pide un reporte a BI o cruza a mano archivos de cada cadena. Espera horas o días, y cuando llega la respuesta el faltante ya pasó. Además, ventas e inventario viven por separado, y le cuesta ver, por ejemplo, que hay producto atorado en el centro de distribución de la cadena. Merece la pena resolverlo porque cada día sin producto en anaquel es venta que no se recupera.

## Qué hace la app

1. **Chat:** el usuario escribe una pregunta en español (o elige una de las preguntas rápidas de la barra lateral) y recibe el hallazgo principal, las cifras en MXN, hasta qué fecha llegan los datos, las posibles causas y de 1 a 3 acciones. «Ver SQL» deja auditar cómo se calculó cada número.
2. **Gráficos y tarjetas:** si el usuario pide «gráfico de venta semanal por cadena» o «un tablero de salud de inventario», la app lo dibuja y permite descargar los datos.
3. **Tablero:** diagnóstico fijo de productos sin existencia, por agotarse, con inventario dudoso y con exceso, con filtro por cadena. **No usa IA**, así que funciona siempre.

## La pieza de IA

- **Qué usa:** API de Gemini (capa gratuita) con herramientas (*function calling*). El modelo principal es `gemini-3.8-flash`, con tres respaldos (`gemini-3.6-flash`, `gemini-3.5-flash-lite` y `gemini-3.1-flash-lite`), todos en `config.yaml`.
- **Por qué esa opción:** el problema es traducir lenguaje natural a consultas sobre datos tabulares y explicar el resultado. Un RAG recupera fragmentos de texto, pero aquí los números hay que calcularlos, no recuperarlos; y un modelo pequeño de Hugging Face escribe SQL con menos fiabilidad y es más lento en un Space gratuito.
- **Qué pasa si falla:** si Gemini responde «saturado», la app reintenta (a los 2 y 5 segundos) y después prueba el siguiente modelo de la lista. Lo mismo si se acaba la cuota o el modelo ya no existe. Si todos fallan, o no hay conexión, o falta la clave, el usuario ve un mensaje claro y el Tablero sigue disponible. Nunca ve un error técnico: el detalle va al log. Además hay un tope de 12 preguntas por sesión y 150 por día para cuidar la cuota gratuita.
- **Dónde está la clave:** en Settings → Secrets de Streamlit Cloud (`GEMINI_API_KEY`). No está en el código ni en el repositorio.

## Cómo la he construido

- **Herramientas:** Claude (en claude.ai y con su agente de código) para diseñar, escribir y probar el código; Gemini API (`google-genai`) como la IA de la app; DuckDB y pandas para los datos; Streamlit y Streamlit Community Cloud para la interfaz y el despliegue; GitHub para el repositorio.
- **Fichero de contexto del agente:** [AGENTS.md](AGENTS.md) (y `CLAUDE.md`, que apunta a él).
- **Prompts clave** (copiados tal cual):
- 
  1. «Eres un desarrollador senior de Python. Construye completa la app «Casa Lumina · Sell Out & Inventarios» siguiendo esta especificación. No me hagas preguntas: si algo no está definido, elige lo más razonable y dime qué elegiste.

PROBLEMA:
El KAM o analista comercial de una empresa de consumo masivo vende a través de cadenas de autoservicio. Hoy depende de que BI le prepare reportes o cruza archivos a mano, y cuando llega la respuesta el faltante ya pasó. Quiero que pregunte en español, sin saber SQL, y reciba cifras, gráficos y acciones.

MUNDO FICTICIO (todo inventado; nada real)
Empresa Casa Lumina. Productos con segmento y presentación, EAN que empiezan con 299 y unas 250 tiendas. Ventas diarias de ene-2025 a oct-2026 e inventario diario de 2026 (inventario en tienda, en tránsito, en CEDIS, unidades ordenadas), generados con semilla fija. Deja a propósito 1 EAN y 2 tiendas fuera de los catálogos y muéstralos como «SIN CATALOGO». Crea escenarios coherentes (quiebres, inventario atorado en CEDIS, sobreinventario, marcas que crecen y marcas que caen).

FUNCIONALIDADES (máximo tres)
1. Chat: preguntas en español sobre ventas e inventario. Responde con hallazgo, cifras en MXN sin IVA, fecha de corte de los datos, posibles causas, qué no se puede saber y de 1 a 3 acciones. Incluye «Ver SQL» para auditar y preguntas rápidas en la barra lateral.
2. Gráficos y tarjetas de resumen cuando el usuario los pide, con descarga de los datos.
3. Tablero de diagnóstico (sin existencia, por agotarse, inventario dudoso, exceso) con filtro por cadena, que funciona SIN IA.

ARQUITECTURA
- Python 3.12 y Streamlit, desplegable en Streamlit Community Cloud. Archivo principal app.py.
- La IA es la API de Gemini con el SDK google-genai y function calling (herramientas run_sql y show_visual). Solo habla con Gemini el módulo llm.py.
- DuckDB ejecuta todas las consultas sobre parquets. El modelo nunca calcula cifras: solo escribe SQL y explica.
- Guardrails de SQL: un solo SELECT, sin leer archivos ni ejecutar comandos, máximo 200 filas y 30 segundos.
- config.yaml con el modelo principal y una lista de modelos de respaldo, límites (máximo 10 pasos del modelo, 12 preguntas por sesión, 150 por día), rutas y umbrales.
- Archivos: app.py, agent.py (prompt, herramientas y guardrails), llm.py, tema.py y visuales.py, vistas.sql, negocio.md, config.yaml, generar_datos_sinteticos.py, requirements.txt, y si faltan datos al arrancar la app los genera sola.

LENGUAJE DE KAM
El usuario nunca ve códigos internos (QUIEBRE, EN_TRANSITO, SIN_PIPELINE…). Crea un diccionario de etiquetas y úsalo en gráficos, tablas y respuestas. Además traduce automáticamente cualquier código que el modelo escriba en su texto.

DISEÑO
Paleta de tonos azules, encabezado azul oscuro con los datos ficticios a la vista, barra lateral oscura con preguntas rápidas, gráficos limpios y legibles.


ENTREGA
Entrega una base inicial para ir ajustando después. 
  2. «Me gusta el mundo ficticio. Agreguemos más clientes (no solo tres) y algunos productos más, sin exagerar. Usa una paleta de tonos más azules y recuerda que este es mi proyecto escolar»
  3. «Traduce los códigos internos del diagnóstico a lenguaje de KAM, en los gráficos, las tablas y las respuestas del asistente.»
  4. «Construyamos ahora el repositorio completo del reto y lo vamos afinando con las pruebas.»
  5. «La app falla cuando Gemini se satura. ¿Conviene simplificar la arquitectura, usar un RAG o mantener la API? Propón cómo hacerla más resistente.»
     
- **Qué delegué al agente y qué revisé a mano:**
  - *Delegué:* escribir el generador de datos ficticios, el código de la app, la capa de Gemini con su manejo de errores y las pruebas automáticas.
  - *Revisé a mano:* todo lo que se despliega. Subí cada archivo a GitHub, probé la app real en Streamlit Cloud con mis propias preguntas, puse la clave yo misma en Secrets y comprobé los mensajes de error. Esas pruebas encontraron cosas que las pruebas automáticas no vieron: Gemini saturado, un nombre de modelo que no existía para mi cuenta y una función que faltaba por subir un archivo sin otro.
  - *Decidí yo:* el mundo ficticio, la paleta azul, las tres funcionalidades, el lenguaje de KAM y qué mostrar en las capturas.

## Prueba y mejora

| Quién la probó | Qué probó | Qué pasó | Qué cambié |
|---|---|---|---|
| Yo, como usuaria | «¿Dónde estoy perdiendo venta por falta de producto y por qué?» con Gemini activado | `gemini-3.8-flash` respondió «saturado» (503) tres veces; después la app respondió en cerca de un minuto con el hallazgo y las acciones, pero con códigos internos (`SIN_PIPELINE`, `EN_TRANSITO`) en el texto | Reintentos automáticos, cadena de cuatro modelos y `tema.etiquetar_texto`, que traduce los códigos a lenguaje de KAM |
| Yo, como usuaria | Cambiar el modelo por `gemini-2.5-flash` | «El modelo de IA configurado no está disponible» (error 404) | Volví a los modelos 3.x, que sí están disponibles para mi cuenta |
| Yo, como usuaria | «Hazme una gráfica de precio…» (valor entre unidades por marca) | Dibujó el gráfico correcto, incluida la barra «SIN CATALOGO»; el precio promedio mezcla presentaciones distintas | Nada por ahora: lo dejé anotado como límite y como mejora futura (que compare por segmento y presentación, datos que el catálogo ya trae) |
| Yo, como usuaria | La pregunta rápida «Dame un tablero de salud de inventario por cadena» | Dibujó las tarjetas y el gráfico, pero cerró con «No logré cerrar la consulta en los pasos permitidos» porque agotó los 6 pasos sin escribir la conclusión | Subí el límite a 10 pasos, en el último paso obligo al modelo a cerrar con texto y, si ya dibujó algo, la app muestra un mensaje útil en vez de un aviso de fallo. Después de eso respondió bien y más rápido |
| Yo, como usuaria | Actualizar `agent.py` sin subir `tema.py` | La app falló porque `agent.py` llamaba a una función que aún no existía en `tema.py` | Subí `tema.py`; la regla de subir juntos los archivos que dependen entre sí quedó en `AGENTS.md` |

## Ejecutar en local (opcional)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt    # Python 3.12
python generar_datos_sinteticos.py # una vez: crea data/
python selftest.py                 # motor de consultas (debe terminar con TODO OK)
python selftest_llm.py             # capa de IA sin red (debe terminar con TODO OK)
# Pon tu clave de Gemini en .streamlit/secrets.toml (ver .streamlit/secrets.toml.example)
streamlit run app.py
```

Sin clave, la app arranca igual: el Tablero funciona y el chat avisa que la IA no está activa.

## Datos

Los crea `generar_datos_sinteticos.py` (determinista, semilla fija): 6 cadenas, 248 tiendas, 5 marcas, 66 productos, ventas diarias de ene-2025 a oct-2026 e inventario diario de 2026. Un producto y dos tiendas quedan fuera de los catálogos **a propósito**, para probar cómo se comporta la app ante datos incompletos («SIN CATALOGO»). En Streamlit Cloud la app genera los datos sola al arrancar si no los encuentra.

## Capturas
1. **La app funcionando:** la respuesta a «Grafica de Inventarios» con las acciones y «Ver SQL».
<img width="882" height="671" alt="Captura de pantalla 2026-10-31 a la(s) 10 20 38 p m" src="https://github.com/user-attachments/assets/2e8fc3ee-7a31-4bd5-b292-cc0d6fae32cf" />

2. **La app ante un error:** el mensaje «El servicio de IA está saturado en este momento. Intenta de nuevo en un minuto.»
<img width="926" height="462" alt="Captura de pantalla 2026-10-31 a la(s) 10 21 30 p m" src="https://github.com/user-attachments/assets/5e451df9-6f77-4182-8ec1-8a4cf5277c62" />

4. **Mi trabajo con la IA:** una conversación con el asistente donde se ve uno de los prompts clave y lo que devolvió.

<img width="582" height="657" alt="Captura de pantalla 2026-10-31 a la(s) 10 24 08 p m" src="https://github.com/user-attachments/assets/aca2bc75-fb4b-4512-99ac-4a02bbfdab0b" />

<img width="645" height="683" alt="Captura de pantalla 2026-10-31 a la(s) 10 22 36 p m" src="https://github.com/user-attachments/assets/e6017a08-5fbe-4907-95d9-30ff1a2cd8d7" />


