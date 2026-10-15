import re
from pathlib import Path

from .config import load_config
from .paths import session_dir
from .prompts import build_prompt
from .provider import infer
from .store import load_session, save_session


def _read_user_files(session_id: str) -> str:
    user_dir = session_dir(session_id) / "fuentes" / "usuario"
    chunks = []
    if user_dir.exists():
        for path in sorted(user_dir.glob("*")):
            if path.is_file() and path.suffix.lower() in (".txt", ".md"):
                chunks.append(f"[archivo: {path.name}]\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(chunks)


def _verify_citations(plan: str) -> None:
    sections = re.split(r"(?=^#{1,6}\s)", plan, flags=re.MULTILINE)
    for section in sections:
        if not section.strip():
            continue
        if not re.search(r"\[cita:\s*[^\]]+\]", section):
            # Allow title-only or tiny sections without citations.
            if re.search(r"\w{20,}", section):
                raise RuntimeError("El plan no tiene citas suficientes.")


def generate_plan(session_id: str) -> None:
    session = load_session(session_id)
    logro = session.get("logro", "")
    fuentes = session.get("fuentes", [])
    root = session_dir(session_id)
    fuentes_texto = []

    if "modelo" in fuentes:
        constraints, body = build_prompt(
            "planner.synthesize.md",
            {"logro": logro},
        )
        synthesis = infer("tutor", body, constraints)
        target = root / "fuentes" / "apuntes_modelo" / "sintesis_inicial.md"
        target = root / "fuentes" / "apuntes_modelo" / "sintesis_inicial.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(synthesis, encoding="utf-8")
        fuentes_texto.append(f"[fuentes/apuntes_modelo/sintesis_inicial.md]\n{synthesis}")

    if "web" in fuentes:
        constraints, body = build_prompt(
            "planner.synthesize.md",
            {"logro": logro},
        )
        synthesis = infer("tutor", body, constraints)
        target = root / "fuentes" / "apuntes_web" / "busqueda_01.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(synthesis, encoding="utf-8")
        fuentes_texto.append(f"[fuentes/apuntes_web/busqueda_01.md]\n{synthesis}")

    if "usuario" in fuentes:
        user_content = _read_user_files(session_id)
        if user_content:
            fuentes_texto.append(f"[fuentes/usuario]\n{user_content}")

    all_fuentes = "\n\n".join(fuentes_texto)
    constraints, body = build_prompt(
        "planner.plan.md",
        {"logro": logro, "fuentes": all_fuentes},
    )
    plan = infer("tutor", body, constraints)
    _verify_citations(plan)
    (root / "plan.md").write_text(plan, encoding="utf-8")
    append_plan_log(session_id)


def append_plan_log(session_id: str) -> None:
    from .store import append_log

    append_log("plan_generated", session_id, {})


def parse_plan(plan_text: str) -> tuple[list[str], dict]:
    concepts = []
    in_concepts = False
    rubric = {}
    in_rubric = False

    for raw_line in plan_text.splitlines():
        line = raw_line.strip()
        lower = line.lower()
        if re.match(r"^#{1,6}\s", line):
            in_concepts = "secuencia" in lower or "concepto" in lower
            in_rubric = "rubrica" in lower or "rubric" in lower
            continue
        if in_concepts and re.match(r"^(\d+\.|-)\s+", line):
            concept = re.sub(r"^(\d+\.|-)\s+", "", line).strip()
            if concept:
                concepts.append(concept)
        if in_rubric:
            match = re.match(r"^[-*]\s*([A-Za-zÁÉÍÓÚáéíóúüñÑ_ ]+?)\s*[:\-]\s*(.*)$", line)
            if match:
                rubric[match.group(1).strip()] = match.group(2).strip() or match.group(1).strip()
    if not concepts:
        for line in plan_text.splitlines():
            match = re.match(r"^(\d+)\.\s+(.+)$", line.strip())
            if match:
                concepts.append(match.group(2).strip())
    if not rubric:
        rubric = {
            "comprension": "Comprension del concepto",
            "aplicacion": "Aplicacion a problemas",
            "precision": "Precision tecnica",
        }
    return concepts, rubric
