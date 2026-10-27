# Registro de cambios

Todos los cambios notables de este proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [Sin publicar]

### Añadido

- Servicio de aprendizaje independiente de la consola, con diagnóstico sin nota,
  ejercicios persistentes, pistas, consultas libres y resumen final.
- Planes JSON revisables, citas literales verificadas contra snapshots de fuentes
  y copia inmutable del plan aceptado.
- `/accept`, `/continue`, `/plan`, `/sources`, `/sessions`, `/resume`, `/models`
  y selección de sesión mediante `--session`.
- Persistencia atómica de cada intento junto con el progreso y bloqueo de escritor
  único por directorio de datos.
- Validación de configuración, puntajes finitos y respuestas estructuradas;
  mensajes de error recuperables sin inventar calificaciones.

### Cambiado

- Versión del paquete: 0.1.0.
- El evaluador recibe la pregunta exacta y las fuentes del concepto; el tutor usa
  el diagnóstico y los intentos recientes para reforzar el aprendizaje.
- El panel llama a los modelos/proveedores seleccionados. Sin panel, se utiliza
  el evaluador principal. El umbral de varianza predeterminado pasa a 0,05.
- Los prompts de sistema se envían realmente a la API. Las plantillas internas
  están en inglés, sin sufijos de versión, y solicitan respuestas para el alumno
  en español.
- Código, comentarios, claves y rutas internas en inglés; interfaz y documentación
  en español. Los identificadores de dimensión se separan de sus nombres visibles.
- Las credenciales se solicitan sin eco; la asignación a roles se persiste.
- La API requiere HTTPS salvo servidores locales y no sigue redirecciones.
- README ampliado con operación, recuperación, costos, privacidad y límites.

### Corregido

- Una respuesta aprobada avanza de concepto y el último concepto completa el plan.
- Las pistas y el modo libre no cuentan como intentos ni pierden el ejercicio.
- Las fallas de red, JSON o evaluación no se convierten en notas cero.
- El arranque no genera dos diagnósticos ni hace llamadas a modelos.
- IDs de sesión sin colisiones por creación en el mismo segundo.

### Eliminado

- La opción engañosa de búsqueda web: ahora se ofrecen sólo fuentes importadas
  o apuntes identificados del modelo. No hay búsqueda automática.
- Escrituras redundantes de progreso en scratchpad/JSONL: `state.json` es la fuente
  canónica e incluye la evidencia completa de cada intento.
- Lectores de planes Markdown, migraciones de estado, respaldos automáticos de
  formatos anteriores y alias de prompts para compatibilidad.
- La copia redundante `plan.md`: `/plan` muestra el plan estructurado en la consola.

### Cambios incompatibles

- Se requiere una configuración y sesiones nuevas; no se admiten formatos previos.
- La configuración usa el rol `evaluator`. Las sesiones usan `goal`, `source_types`
  y `state.json`; las fuentes se guardan en `sources/user/` y `sources/model/`.
- La rúbrica usa identificadores en inglés y objetos con `label` y `description`
  en español. Los archivos y textos del usuario conservan su idioma original.

## [0.0.1] - 2026-10-16

### Añadido

- Estructura inicial del paquete `arnes`.
- Modulo `paths` con resolucion del directorio `~/.arnes/` y override por `ARNES_HOME`.
- Modulo `config` con carga, guardado y validacion de `config.json`.
- Modulo `credentials` con carga y guardado de `credentials.json` con permisos `0600` en Unix.
- Modulo `prompts` con parser de frontmatter YAML minimalista y prompts por defecto.
- Modulo `store` con persistencia de sesiones y estado en JSON.
- Modulo `orchestrator` con maquina de estados pedagogica determinista.
- Modulo `validator` con validacion de restricciones y fallback determinista.
- Modulo `provider` con interfaz abstracta `InferenceProvider` y adaptador `OpenRouterProvider`.
- Modulo `evaluator` con panel de evaluadores, agregacion por mediana y umbral compuesto.
- Modulo `planner` con generacion de plan a partir de logro y fuentes, con citas obligatorias.
- Modulo `commands` con `/help`, `/settings`, `/connect`, `/new`, `/status`, `/quit`.
- Modulo `repl` con bucle interactivo usando `prompt_toolkit` y `rich`.
- Modulo `cli` con entry point `arnes`.
- Script `install.sh` para macOS, Linux y WSL.
- Script `install.ps1` para Windows.
- README con instrucciones de instalacion, uso y desinstalacion.

[Sin publicar]: https://github.com/lflamonega/arnes/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/lflamonega/arnes/releases/tag/v0.0.1
