# AGENTS.md · Casa Lumina · Sell Out & Inventarios

> Este fichero lo leen los agentes de programación antes de tocar el código.
> Para Claude Code existe un `CLAUDE.md` con una sola línea que apunta aquí.

## Qué es este proyecto

Asistente que responde en español preguntas de ventas e inventario en tienda a los KAMs y analistas comerciales de Casa Lumina, una empresa **ficticia** de consumo masivo, a partir de datos **ficticios**. Incluye un Tablero que funciona sin IA.

## Cómo está hecho (prueba kath)

- Python 3.12.
- Interfaz: Streamlit (ruta A, Streamlit Community Cloud). Archivo principal: `app.py`.
- IA: API de Gemini con el SDK `google-genai`, **solo en `llm.py`**. Los modelos están en `config.yaml` (`modelo` y `modelo_respaldo`).
- Datos: parquets en `data/` consultados con DuckDB. Son ficticios y los crea `generar_datos_sinteticos.py` (determinista).
- Archivos:
  - `app.py`: interfaz (Chat y Tablero).
  - `agent.py`: prompt del modelo, herramientas (`run_sql`, `show_visual`) y guardrails de SQL.
  - `llm.py`: todo lo que habla con Gemini, incluido el manejo de errores (cuota, conexión, clave).
  - `tema.py` y `visuales.py`: colores azules, etiquetas en lenguaje de KAM y gráficos.
  - `vistas.sql`: vistas de diagnóstico. `negocio.md`: definiciones y ejemplos para el modelo. `config.yaml`: rutas, columnas y umbrales.
  - `selftest.py` (motor de consultas), `selftest_llm.py` (capa de IA sin red), `check_data.py` (valida parquets).
- La especificación completa está en `especificacion.md`.

## Reglas

- La clave de la API va SIEMPRE en secretos (`st.secrets["GEMINI_API_KEY"]`; en local, `.streamlit/secrets.toml`, que está en `.gitignore`). Nunca en el código, en el README ni en el chat.
- Cada llamada a la API va dentro de `try/except` y muestra un mensaje claro para el usuario. El usuario nunca ve un error técnico; el detalle va al log.
- Textos de la interfaz y de las respuestas en español sencillo, **en lenguaje de KAM**: nada de códigos internos (`QUIEBRE`, `EN_TRANSITO`, `pipeline`...). La traducción vive en `tema.ETIQUETAS`.
- Si agregas un valor nuevo de situación en `vistas.sql`, agrega su etiqueta y su color en `tema.py` (`selftest.py` lo verifica).
- Todo dato es ficticio. No uses nombres reales de empresas, cadenas, marcas, personas ni códigos de barras reales. Los EAN de ejemplo empiezan con 299.
- Los números los calcula SIEMPRE DuckDB, nunca el modelo.
- Cambios pequeños: uno por petición. Al terminar, explica qué has cambiado y por qué.
- Si añades una librería, añádela también a `requirements.txt` y dilo.
- Tras cualquier cambio en `agent.py`, `llm.py`, `tema.py`, `vistas.sql` o `config.yaml`, corre `python selftest.py` y `python selftest_llm.py`.

## Cómo comprobar que funciona

- Local: `pip install -r requirements.txt`, luego `python generar_datos_sinteticos.py` (una vez), `python selftest.py`, `python selftest_llm.py` y `streamlit run app.py` (con `.streamlit/secrets.toml`).
- Streamlit Cloud: haz push y revisa la app; la clave va en Settings → Secrets.
- Casos de prueba (entrada → lo que esperamos):
  1. «¿Dónde estoy perdiendo venta por falta de producto?» → respuesta en lenguaje de KAM con cifras en MXN, fecha de corte y acciones; sin códigos internos.
  2. «Gráfico de venta semanal por cadena» → gráfico de líneas con seis cadenas.
  3. «Dame una receta de tacos» → la app dice amablemente que no puede ayudar con eso y ofrece dos preguntas válidas.
  4. Cuota agotada → mensaje claro y el Tablero sigue funcionando.

## Qué no hacer

- No borres ni reescribas el README sin preguntar.
- No cambies el modelo ni la arquitectura (DuckDB calcula, la IA traduce y explica) sin preguntar.
- No debilites los guardrails de SQL de `agent._ejecutar` sin preguntar.
- No subas `data/` modificado a mano ni archivos `.env` o `secrets.toml`.
- No hagas push ni despliegues sin que yo lo haya revisado.
