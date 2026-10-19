# Casa Lumina · Sell Out & Inventarios

**Enlace a la app:** [PENDIENTE: https://…streamlit.app]
**Autor/a:** Kath Bejarano

> Todos los datos de esta app son **ficticios**: la empresa (Casa Lumina), las cadenas, las marcas, las tiendas, los códigos de barras y las cifras están inventados.

## Pitch

1. Los equipos comerciales de consumo masivo no ven a tiempo dónde les falta producto en tienda, y cada vez que quieren saberlo dependen de que alguien les prepare un reporte.
2. Esta app deja preguntar en español por ventas e inventario, responde con gráficos y acciones, y trae un Tablero de diagnóstico que no necesita IA.
3. La IA traduce una pregunta nueva a una consulta correcta, cruza ventas con inventario y explica el resultado con prudencia; los números los calcula siempre una consulta, no el modelo.
4. [PENDIENTE: qué aprendí de la prueba y qué cambié.]
5. [PENDIENTE: qué haría después, con un dato o ejemplo concreto.]

## El problema

El KAM o analista comercial de una empresa de consumo masivo vende a través de cadenas de autoservicio. Hoy, para saber dónde pierde venta por falta de producto o cómo va una cadena contra el mes anterior, le pide un reporte a BI o cruza a mano archivos de cada cadena. Espera horas o días, y cuando llega la respuesta el faltante ya pasó. Además, ventas e inventario viven por separado, y le cuesta ver, por ejemplo, que hay producto atorado en el centro de distribución de la cadena.

## Qué hace la app

1. **Chat:** escribes una pregunta en español (o eliges una de las preguntas rápidas) y recibes el hallazgo principal, las cifras, las posibles causas y de 1 a 3 acciones. «Ver SQL» deja auditar cómo se calculó cada número.
2. **Gráficos y tarjetas:** pides «gráfico de venta semanal por cadena» o «un tablero de salud de inventario» y la app lo dibuja; puedes descargar los datos.
3. **Tablero:** diagnóstico fijo de faltantes, productos por agotarse, inventario dudoso y exceso, con filtro por cadena. **No usa IA**, así que funciona siempre.

## La pieza de IA

- **Qué usa:** API de Gemini (capa gratuita) con herramientas (*function calling*). Modelos en `config.yaml`.
- **Por qué esa opción:** el problema es traducir lenguaje natural a consultas sobre datos tabulares y explicar el resultado. Un RAG recupera fragmentos de texto, pero aquí los números hay que calcularlos; y un modelo pequeño de Hugging Face escribe SQL con menos fiabilidad.
- **Qué pasa si falla:** si se acaba la cuota, la app prueba un modelo de respaldo y, si tampoco hay, muestra un mensaje claro y deja el Tablero disponible. Lo mismo si no hay conexión, si falta la clave o si el servicio está saturado. El usuario nunca ve un error técnico (el detalle va al log de la app). Además hay un tope de 12 preguntas por sesión y 150 por día.

## Cómo la he construido

- **Herramientas:** [Claude]
- **Fichero de contexto del agente:** [AGENTS.md](AGENTS.md) (y `CLAUDE.md`, que apunta a él).
- **Prompts clave:** ver [docs/bitacora_prompts.md](docs/bitacora_prompts.md). 
- **Qué delegué al agente y qué revisé a mano:** ver la bitácora.

## Prueba y mejora

| Quién la probó | Qué probó | Qué pasó | Qué cambié |
|---|---|---|---|
| [PENDIENTE] | | | |

## Datos

Los crea `generar_datos_sinteticos.py` (determinista, semilla fija): 6 cadenas, 248 tiendas, 5 marcas, 66 productos, ventas diarias de ene-2025 a oct-2026 e inventario diario de 2026. Un producto y dos tiendas quedan fuera de los catálogos **a propósito**, para probar cómo se comporta la app ante datos incompletos («SIN CATALOGO»).

## Ejecutar en local (opcional)

```bash
./setup.sh                         # crea .venv e instala dependencias
source .venv/bin/activate
python generar_datos_sinteticos.py # una vez: crea data/
python selftest.py                 # motor de consultas (debe terminar con TODO OK)
python selftest_llm.py             # capa de IA sin red (debe terminar con TODO OK)
# Pon tu clave de Gemini en .streamlit/secrets.toml (ver .streamlit/secrets.toml.example)
streamlit run app.py
```

Sin clave, la app arranca igual: el Tablero funciona y el chat avisa que la IA no está activa.

## Capturas

[PENDIENTE: la app funcionando, la app ante un caso límite o error (p. ej. cuota agotada), un momento de trabajo con la IA y la prueba. Sin ninguna clave a la vista.]
