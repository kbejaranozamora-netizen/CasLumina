# Bitácora de proceso con IA

**Proyecto:** Casa Lumina · Sell Out & Inventarios
**Autora:** Kathia Bejarano Zamora
**Herramientas de IA:** Claude (diseño, código y pruebas) · Gemini API (la IA de la app)
**Periodo:** 12/10/2026 – 31/10/2026

Este documento respalda el apartado 5 de la entrega («Proceso con IA»). Registra, en orden cronológico, qué pedí al asistente, qué produjo y qué decidí o verifiqué yo. Solo incluye lo que ocurrió realmente.

## Resumen

| Fase | Fechas | Resultado |
|---|---|---|
| 1. Definición | 12/10 | Alcance del reto, mundo ficticio y lenguaje de KAM |
| 2. Construcción | 12/10 – 18/10 | Repositorio completo y primer despliegue en Streamlit Cloud |
| 3. Integración con Gemini | 19/10 – 26/10 | Chat con IA funcionando y errores reales documentados |
| 4. Resiliencia | 26/10 – 31/10 | Reintentos, cadena de cuatro modelos y traducción automática de códigos |

## Registro detallado

### Fase 1 · Definición

| Fecha | Solicitud | Aportación del asistente | Decisión o verificación mía |
|---|---|---|---|
| 12/10 | Analizar mi reto y mi chatbot existente y opinar | Resumió las restricciones (sin API de pago, despliegue público, clave en secretos, manejo de fallos) y señaló los riesgos de reutilizar el chatbot | Adaptar mi chatbot de sell out e inventarios como entregable |
| 12/10 | Revisar la carpeta completa del chatbot | Auditó el código: encontró una clave de API real en un `.env`, nombres reales de cadenas y marcas en los datos «sintéticos» y que el único punto de contacto con el LLM era una función (`ask`) | Crear una versión separada para el reto, con otra clave y sin datos reales |
| 12/10 | Ir despacio y en sintonía antes de arrancar | Leyó plantillas y enunciado y propuso el orden: especificación → repositorio → Gemini → prueba → entrega | Aprobar cada decisión paso a paso |
| 12/10 | Trabajar sola, conservar el Tablero y ficcionalizar todo | Propuso el mundo ficticio de Casa Lumina (cadenas, marcas, productos) y qué eliminar del proyecto original | Aprobé el mundo ficticio y pedí más cadenas, pocos productos más y una paleta azul |
| 12/10 | Traducir a lenguaje de KAM | Creó un glosario de KAM y lo aplicó a gráficos, tablas y respuestas | Elegí el lenguaje de KAM para que el usuario nunca vea códigos internos |
| 12/10 | Ayuda con las preguntas guía de la Pauta 1 | Redactó borradores de las tres respuestas | Los revisé y los usé como base de mi respuesta |

### Fase 2 · Construcción

| Fecha | Solicitud | Aportación del asistente | Decisión o verificación mía |
|---|---|---|---|
| 12/10 | Construir todo primero y afinar después | Generó el repositorio: datos ficticios, tema azul, etiquetas de KAM, capa de Gemini aislada en `llm.py`, pruebas automáticas, especificación, `AGENTS.md` y documentos. Avisó que no pudo probar DuckDB, Streamlit ni Gemini reales | Construir primero y probar ya con la app desplegada |
| 18/10 | Reporté que, con solo `app.py` en GitHub, Streamlit mostraba un error | Explicó que `app.py` importa otros módulos (`llm.py`, `agent.py`…) y que faltaba subir el resto | Subí todos los archivos y la carpeta de configuración, y conecté la app en Streamlit Cloud |

### Fase 3 · Integración con Gemini

| Fecha | Solicitud | Aportación del asistente | Decisión o verificación mía |
|---|---|---|---|
| 19/10 | Responder las preguntas del hito 2 | Redactó respuestas sobre especificación, `AGENTS.md`, qué revisar y por qué API y no RAG | Las usé como base de mis respuestas |
| 26/10 | Pasar al hito 3 | Dio el plan: activar Gemini, comprobar la clave, probar y proteger errores | Creé mi clave de Gemini y la puse solo en Secrets de Streamlit Cloud |
| 26/10 | Reporté que una pregunta tardaba demasiado | Explicó que la pregunta más pesada requiere varias idas y vueltas con el modelo | Esperé; la app respondió |

### Fase 4 · Resiliencia y corrección de errores

| Fecha | Solicitud | Aportación del asistente | Decisión o verificación mía |
|---|---|---|---|
| 26/10 | Pregunté si simplificar, usar un RAG o mantener la API ante un fallo | Explicó que un RAG no calcula números y que el fallo era saturación del servicio (503), no de arquitectura; propuso reintentos y respaldo | Mantuve la API de Gemini y probé los modelos de respaldo |
| 26/10 | Cambié a un modelo 2.5 que sugirió el asistente | Reconoció su error: esos modelos no están disponibles para cuentas nuevas; verificó los nombres vigentes en la documentación de Google | Volví a los modelos 3.x; el error «modelo no disponible» me sirvió como captura de caso de error |
| 26/10 | Compartí una captura con un código interno (`SIN_PIPELINE`) en la respuesta | Detectó que Gemini omitía la regla de no mostrar códigos y escribió una traducción automática (`tema.etiquetar_texto`) | Lo detecté en mi propia prueba y lo documenté como hallazgo |
| 31/10 | Pedí un respaldo ante una posible falla del modelo principal | Implementó una cadena de cuatro modelos con reintentos y actualizó las pruebas | Actualicé `agent.py`, `config.yaml` y `selftest_llm.py` en GitHub |
| 31/10 | Compartí un log con `Falla inesperada` en `etiquetar_texto` | Explicó que subí un `agent.py` nuevo con un `tema.py` antiguo y entregó el `tema.py` correcto | Aprendí a subir juntos los archivos que dependen entre sí; la regla quedó en `AGENTS.md` |
| 31/10 | Compartí un aviso «No logré cerrar la consulta…» en una pregunta rápida | Subió el límite a 10 pasos, forzó una respuesta de texto en el último paso y añadió un mensaje útil si ya hay gráficos | Probé de nuevo: respondió bien y más rápido |

## Reparto de trabajo

| | Detalle |
|---|---|
| **Delegué al asistente** | Generador de datos ficticios, código de la app, capa de Gemini con manejo de errores, pruebas automáticas y borradores de documentos |
| **Revisé a mano** | Todo lo que se despliega: subí cada archivo a GitHub, probé la app real con mis propias preguntas, puse la clave yo misma en Secrets y comprobé los mensajes de error |
| **Decidí yo** | El mundo ficticio, la paleta azul, las tres funcionalidades, el lenguaje de KAM, mantener la API en lugar de un RAG y qué mostrar en las capturas |

Las pruebas con la app real encontraron lo que el asistente no podía ver desde su entorno: Gemini saturado, un modelo que no existía para mi cuenta y una función que faltaba por subir archivos por separado.
