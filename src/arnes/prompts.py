import re
from pathlib import Path

from .paths import prompts_dir

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def parse_simple_yaml(text: str) -> dict:
    lines = [line.rstrip() for line in text.splitlines()]
    nonblank = [line for line in lines if line.strip()]
    return _parse_block(nonblank, 0)


def _parse_block(lines: list[str], base_indent: int) -> dict:
    result = {}
    i = 0
    total = len(lines)
    while i < total:
        line = lines[i]
        indent = len(line) - len(line.lstrip())
        if indent < base_indent:
            break
        if indent > base_indent:
            i += 1
            continue
        stripped = line.strip()
        if stripped.startswith("- "):
            i += 1
            continue
        if ":" not in stripped:
            i += 1
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if value == "":
            j = i + 1
            while j < total and not lines[j].strip():
                j += 1
            if j < total and lines[j].lstrip().startswith("- "):
                items = []
                k = j
                while k < total and lines[k].strip() and (len(lines[k]) - len(lines[k].lstrip())) > indent:
                    item = lines[k].strip()
                    if item.startswith("- "):
                        items.append(_parse_scalar(item[2:].strip()))
                    k += 1
                result[key] = items
                i = k
            else:
                k = j
                while k < total and (not lines[k].strip() or (len(lines[k]) - len(lines[k].lstrip())) > indent):
                    k += 1
                nested = lines[i + 1:k]
                result[key] = _parse_block(nested, indent + 2)
                i = k
        else:
            result[key] = _parse_scalar(value)
            i += 1
    return result


def _parse_scalar(value: str):
    value = value.strip()
    if value == "null" or value == "~":
        return None
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def load_prompt(name: str) -> tuple[dict, str]:
    path = prompts_dir() / name
    if not path.exists():
        return {}, ""
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta = parse_simple_yaml(match.group(1))
    return meta, match.group(2).lstrip("\n")


def build_prompt(name: str, context: dict) -> tuple[dict, str]:
    meta, body = load_prompt(name)
    constraints = meta.get("constraints", {}) if isinstance(meta.get("constraints"), dict) else {}

    def replacer(match):
        key = match.group(1)
        if key in context:
            return str(context[key])
        return match.group(0)

    rendered = re.sub(r"\{(\w+)\}", replacer, body)
    return constraints, rendered


DEFAULT_PROMPTS = {}

_DEFAULT_CONTENT = {
    "tutor.system.md": """---
role: tutor
constraints:
  max_tokens: 300
  forbidden_patterns:
    - "la respuesta es"
    - "el resultado es"
    - "la solucion es"
---

Eres un tutor pedagogico. Tu trabajo es ayudar al estudiante a aprender, no darle respuestas.

Reglas absolutas:
- Nunca des la respuesta completa a un problema.
- Nunca resuelvas el problema por el estudiante.
- Si el estudiante pide la respuesta, responde con una pregunta que lo guie.
- Termina siempre con una pregunta o una invitacion a intentar.
- Usa un lenguaje claro, directo, sin condescendencia.
- No uses emojis.

Contexto:
- Logro del estudiante: {logro}
- Concepto actual: {concepto}
- Nivel de dominio: {mastery}
""",
    "tutor.present.md": """---
role: tutor
action: present
constraints:
  max_tokens: 300
  must_end_with_question: true
  forbidden_patterns:
    - "la respuesta es"
    - "el resultado es"
---

Presenta el concepto "{concepto}" al estudiante.

Logro del estudiante: {logro}

Fuentes disponibles:
{fuentes}

Explica el concepto de forma breve y clara. No des la respuesta a ningun ejercicio. Termina con una pregunta para verificar comprension.
""",
    "tutor.hint.md": """---
role: tutor
action: hint
constraints:
  max_tokens: 150
  must_end_with_question: true
  forbidden_patterns:
    - "la respuesta es"
    - "el resultado es"
---

El estudiante esta trabado en el concepto "{concepto}".

Su ultimo intento fue: {ultimo_intento}

Da una pista que lo ayude a avanzar sin revelar la respuesta. Termina con una pregunta.
""",
    "tutor.feedback.md": """---
role: tutor
action: feedback
constraints:
  max_tokens: 250
---

El estudiante respondio al concepto "{concepto}".

Su respuesta fue: {respuesta}

Puntajes obtenidos:
{puntajes}

Da feedback especifico. Senala que estuvo bien y que se puede mejorar. No des la respuesta correcta.
""",
    "evaluator.system.md": """---
role: evaluador
constraints:
  response_format: json
---

Eres un evaluador pedagogico. Tu trabajo es puntuar respuestas de estudiantes contra una rubrica.

Reglas:
- Se objetivo. No premies respuestas largas ni castigues respuestas cortas.
- Si la respuesta es ambigua, puntua bajo.
- No inventes criterios fuera de la rubrica.
- Devuelve SOLO un JSON valido, sin texto adicional.

Formato de salida:
{"dimension1": 0.0, "dimension2": 0.0, ...}
""",
    "evaluator.rubric.md": """---
role: evaluador
action: rubric
constraints:
  response_format: json
---

Evalua la siguiente respuesta contra la rubrica del concepto "{concepto}".

Dimensiones:
{rubric_dimensions}

Respuesta del estudiante:
{respuesta}

Puntua cada dimension de 0.0 a 1.0. Devuelve SOLO un JSON.
""",
    "planner.synthesize.md": """---
role: planner
action: synthesize
constraints:
  max_tokens: 2000
---

Vas a preparar apuntes sobre el siguiente logro de aprendizaje:

{logro}

Escribe una sintesis estructurada en Markdown con:
- Conceptos cubiertos
- Prerrequisitos inferidos
- Vacios detectados

Se breve pero completo. No inventes datos. Si no estas seguro de algo, marcalo como incierto.
""",
    "planner.plan.md": """---
role: planner
action: plan
constraints:
  max_tokens: 2000
---

Vas a generar un plan de aprendizaje para el siguiente logro:

{logro}

Fuentes disponibles:

{fuentes}

Genera un plan en Markdown con:
- Logro esperado
- Fuentes usadas
- Secuencia de conceptos (numerada)
- Rubrica derivada (3 a 5 dimensiones)
- Umbral (agregado, piso dimensional, varianza maxima)

REGLA CRITICA: Cada elemento de la secuencia debe tener una cita en formato [cita: archivo, seccion]. Si no podes citar, no lo incluyas.

Devuelve SOLO el plan en Markdown.
""",
    "fallback.md": """---
role: sistema
---

No se pudo generar una respuesta valida. Intenta reformular tu pregunta o pedi una pista.
""",
}


def ensure_default_prompts() -> None:
    target = prompts_dir()
    target.mkdir(parents=True, exist_ok=True)
    for name, content in _DEFAULT_CONTENT.items():
        destination = target / name
        if not destination.exists():
            destination.write_text(content, encoding="utf-8")
