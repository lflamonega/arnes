# arnes

Tutor por terminal para aprendizaje autodidacta. Convierte un objetivo en un plan
basado en fuentes, propone ejercicios y evalúa las respuestas con un modelo
distinto del tutor. El avance se decide por código, no por el tutor.

Requiere **Python 3.11 o superior**, una API compatible con OpenAI Chat Completions
(OpenRouter por defecto) y modelos que admitan salida JSON. Las llamadas pueden
tener costo. No incluye modelos ni credenciales.

## Instalación

Desde este repositorio:

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
python -m pip install -e .
arnes --help
```

También se puede instalar aislado con `pipx`:

```bash
pipx install git+https://github.com/lflamonega/arnes.git
```

Los instaladores `install.sh` y `install.ps1` automatizan la instalación con pipx.
Conviene leerlos antes de ejecutarlos.

## Primer recorrido

```text
arnes
/connect       → proveedor, clave oculta y URL base
/settings      → opción 1: modelos tutor y evaluador (deben ser distintos)
/models        → IDs disponibles en el proveedor del tutor
/new           → objetivo, archivos opcionales y confirmación de envío a la API
/accept        → aceptar el plan si no lo aceptaste durante /new
```

1. **Fuentes.** Se importan archivos `.txt`/`.md` UTF-8 y/o se generan apuntes del
   modelo. Se copian localmente; cambiar los originales no modifica la sesión.
2. **Plan.** Se genera una secuencia de hasta 12 conceptos, con objetivos
   verificables, rúbrica y citas literales. Cada cita debe aparecer en una fuente.
3. **Revisión.** Podés editar `plan.json` antes de `/accept` y verlo en español con
   `/plan`. No se guarda una segunda representación en Markdown. Aceptarlo congela
   una copia en `session.json`; para cambiar un plan aceptado, creá otra sesión.
4. **Diagnóstico.** Se pregunta qué sabés y qué te cuesta. Es autoinforme, sin nota.
5. **Práctica.** El tutor explica un concepto y propone un ejercicio. Se guardan
   tanto la explicación como la pregunta exacta antes de esperar tu respuesta.
6. **Evaluación.** El evaluador recibe esa pregunta, tu respuesta, la rúbrica y las
   fuentes del concepto. Una respuesta aprobada avanza; de lo contrario, se
   prepara otro ejercicio teniendo en cuenta el feedback y los últimos intentos.
7. **Cierre.** Al superar todos los conceptos se muestra un resumen de lo trabajado.

`pista` solicita ayuda sin registrar un intento ni cambiar el ejercicio.
`libre` permite consultas sin nota; `volver` retoma el punto anterior.

### Fuentes y límites

- **No hay búsqueda web automática.** Para usar una página web, guardá el material
  relevante como texto e importalo indicando su procedencia.
- Los apuntes del modelo se etiquetan como **no verificados**. Una cita literal
  comprueba trazabilidad, no veracidad ni calidad pedagógica.
- Se admiten hasta 20 archivos y 60.000 caracteres de fuentes en total. No se
  truncan silenciosamente. Dividí objetivos grandes en varias sesiones.
- No se procesan PDF, imágenes, audio ni documentos binarios.
- El contexto incluye las fuentes citadas por el concepto, no sólo sus nombres.
  Esto puede consumir bastantes tokens; preferí fuentes breves y pertinentes.

## Comandos

| Comando | Función |
|---|---|
| `/help` | Comandos y atajos |
| `/connect` | Credenciales y asignación real a un rol |
| `/settings` | Roles, panel, umbrales y visualización de puntajes |
| `/models [proveedor]` | Listar modelos disponibles |
| `/new` | Crear una sesión |
| `/plan` | Mostrar el plan |
| `/plan generar` | Generar o regenerar un borrador con las fuentes guardadas |
| `/accept` | Validar y aceptar `plan.json` |
| `/sources` | Fuentes, procedencia y tamaño |
| `/sessions` | Listar sesiones |
| `/resume ID` | Retomar una sesión concreta |
| `/continue` | Mostrar el ejercicio guardado o generar el siguiente |
| `/status` | Estado, progreso y último feedback |
| `/quit` | Salir |

`arnes --session ID` abre una sesión concreta. Sin argumento se retoma la más
reciente, incluso si quedó como borrador. El arranque no hace llamadas a la API.
Ctrl+C cancela la operación actual; Ctrl+D sale. No hay modo one-shot.

## Evaluación

Sin panel se usa una vez el modelo del rol evaluador (`evaluator` en la
configuración). Con panel se llama una vez
a **cada modelo configurado**, con el mismo contexto y sin mostrarle las notas
anteriores ni las de sus pares.

Se calcula la mediana por dimensión y luego el promedio de esas medianas. Los
umbrales predeterminados son:

| Criterio | Valor |
|---|---:|
| Promedio mínimo | 0,75 |
| Piso para cada dimensión | 0,50 |
| Máxima varianza poblacional entre evaluadores, por dimensión | 0,05 |

La varianza es cero con un único evaluador: no mide incertidumbre en ese caso.
Si el panel discrepa por encima del umbral, la evaluación es **inconclusa** y no
avanza; se propone otro ejercicio. Si falla una API, el JSON es inválido o falta
una dimensión, **no se registra ningún intento ni se inventa una nota cero**.
Reenviá tu respuesta para intentar evaluar de nuevo.

Ejemplo de `config.json` con varios proveedores; reemplazá los IDs por modelos
reales y configurá las credenciales correspondientes con `/connect`:

```json
{
  "roles": {
    "tutor": {"provider": "openrouter", "model": "organization/tutor-model", "temperature": 0.7},
    "evaluator": {"provider": "openrouter", "model": "organization/evaluator-model", "temperature": 0.0}
  },
  "panel": {
    "evaluator_models": [
      "organization/evaluator-model",
      {"provider": "other", "model": "independent-model"}
    ]
  },
  "thresholds": {"aggregate": 0.75, "dimension_floor": 0.5, "variance_max": 0.05},
  "ui": {"show_scores": true}
}
```

Una lista vacía activa sólo el evaluador principal. Se rechazan duplicados y el
mismo par proveedor/modelo del tutor. Los alias de un mismo modelo en proveedores
diferentes no pueden detectarse automáticamente. Los umbrales usados, puntajes
individuales e identidades de evaluadores quedan guardados en cada intento.

Las dimensiones de `plan.json` usan identificadores internos en inglés y nombres
visibles en español. Por ejemplo:

```json
{
  "rubric": {
    "comprehension": {
      "label": "Comprensión",
      "description": "Explica el concepto y justifica su aplicación."
    }
  }
}
```

El evaluador devuelve puntajes con los mismos identificadores; la consola muestra
los nombres de `label`.

Los puntajes de modelos pueden ser incorrectos: terminar un plan **no equivale a
una certificación**. Las reglas del tutor reducen la entrega directa de soluciones,
pero no ofrecen una garantía semántica contra errores o inyección de instrucciones.

## Persistencia y recuperación

```text
~/.arnes/
├── config.json
├── credentials.json
├── history
├── prompts/
├── logs/audit.log
└── sessions/<id>/
    ├── session.json       # objetivo y copia del plan aceptado
    ├── state.json         # pregunta, intentos, notas y progreso (canónico)
    ├── plan.json          # borrador estructurado
    ├── sources.json       # snapshot del contenido de las fuentes
    └── sources/
        ├── user/          # copias de los archivos importados
        └── model/
            └── initial_notes.md
```

`session.json` usa `goal` para el objetivo y `source_types` para los tipos de fuente,
con valores `user` y `model`. Si se rechaza la salida de un plan, se conserva en
`plan.rejected.txt` para poder revisarla.

`state.json` se reemplaza atómicamente: intento, nota y avance se guardan juntos.
Un fallo al generar el siguiente ejercicio no borra la evaluación previa; usá
`/status` y `/continue`. Reiniciar conserva preguntas, pistas y modo libre.
No hay reintentos automáticos de API que generen cobros adicionales ocultos.
Cancelar una petición no garantiza que el proveedor no la haya facturado.

Sólo puede abrirse un proceso de `arnes` por directorio de datos. Un bloqueo del
sistema operativo evita escrituras concurrentes y se libera al terminar el proceso.

Para cambiar el directorio:

```bash
# macOS/Linux
ARNES_HOME=/ruta/a/datos arnes
```

```powershell
# Windows
$env:ARNES_HOME = 'D:\datos\arnes'
arnes
```

### Formato de datos

Sólo se admite el formato actual. No hay migraciones, lectura de planes Markdown
ni compatibilidad con configuraciones, sesiones o prompts de versiones anteriores.
Si ya tenés datos de desarrollo, empezá con un directorio `ARNES_HOME` vacío y
configurá los proveedores y modelos de nuevo. No se convierten ni borran datos
anteriores automáticamente.

Un `config.json` existente debe contener las secciones completas del ejemplo:
`roles`, `panel`, `thresholds` y `ui`. Los valores predeterminados se usan al empezar
sin archivo de configuración, no para completar formatos anteriores.

## Prompts

Los prompts se crean en `~/.arnes/prompts/`. Las plantillas están escritas en inglés
y usan nombres sin sufijos de versión: `planner.notes.md`, `planner.plan.md`,
`tutor.exercise.md`, `tutor.hint.md`, `tutor.free.md` y `evaluator.score.md`.
`tutor.system.md` y `evaluator.system.md` se envían como mensajes de sistema.
Las personalizaciones de estas plantillas no se sobrescriben al iniciar.

El cuerpo usa `{context}` para incluir el contexto JSON. El frontmatter admite
mapas con indentación de dos espacios, listas escalares y restricciones simples:
`max_tokens`, `max_chars`, `response_format: json`, `must_end_with_question`,
`forbidden_patterns` y `required_keys`. No es un parser YAML completo.

`max_tokens` se envía al proveedor; la validación local no confunde palabras con
tokens. Si personalizás un prompt estructurado, conservá el esquema JSON requerido.
Borrar un archivo de prompt hace que se restaure su valor predeterminado al iniciar.

## Privacidad

- Las claves se guardan **sin cifrar** en `credentials.json`; en POSIX el archivo
  tiene permisos `0600`. En Windows se aplican los permisos del directorio del usuario.
- Las fuentes seleccionadas y tus respuestas se envían a los proveedores elegidos.
  No importes material confidencial sin autorización.
- El historial de entrada, las fuentes y los intentos se guardan localmente. El log
  de auditoría registra eventos y modelos, no claves ni cuerpos de peticiones.
- Sólo se permiten URLs base HTTPS, salvo HTTP en `localhost`/loopback para un
  servidor local. El cliente no sigue redirecciones que puedan filtrar el Bearer token.
- No hay telemetría adicional ni llamadas a modelos al iniciar la aplicación.

## Desarrollo

### Idiomas

- **Inglés:** código, comentarios, docstrings, identificadores, claves JSON,
  nombres de archivos y directorios internos, plantillas de prompts y apuntes
  internos generados por el modelo.
- **Español:** interfaz, mensajes, ayuda, títulos y descripciones del plan,
  explicaciones, preguntas, pistas y feedback del tutor. Estos textos se guardan
  tal como se muestran, dentro de los campos del esquema en inglés.
- **Español:** documentación del proyecto.
- Los archivos importados, el objetivo, las respuestas del estudiante y las citas
  conservan su contenido original; no se traducen automáticamente.

### Organización

`learning.py` coordina el aprendizaje sin depender de la terminal;
`orchestrator.py` contiene la decisión pura de avance; `evaluator.py` implementa
la evaluación; `planner.py` y `sources.py` construyen el plan con evidencia;
`commands.py` y `repl.py` son la interfaz. `provider.py` encapsula HTTP y `store.py`
la persistencia.

Comprobaciones básicas, sin suite de tests:

```bash
python -m compileall -q src
python -m arnes.cli --help
python -m arnes.cli --version
```

## Desinstalación

```bash
pipx uninstall arnes
```

Para eliminar también datos, respuestas y claves, borrá el directorio `~/.arnes/`
(o el configurado en `ARNES_HOME`) después de hacer las copias que necesites.

Licencia: MIT.
