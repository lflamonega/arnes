import json
import re
import statistics

from .config import load_config
from .provider import infer


def _extract_json(text: str) -> dict:
    text = text or ""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    candidate = match.group(0) if match else text.strip()
    return json.loads(candidate)


def evaluate(response: str, rubric: dict, concept: dict, config: dict) -> dict:
    if not isinstance(config, dict) or not config:
        config = load_config()
    dimensions = {}
    if isinstance(rubric, dict):
        if "dimensions" in rubric and isinstance(rubric["dimensions"], dict):
            dimensions = rubric["dimensions"]
        else:
            dimensions = rubric
    if not dimensions:
        dimensions = {"comprension": "Comprension general"}

    concept_name = concept.get("concept", "") if isinstance(concept, dict) else str(concept)
    dimensions_text = "\n".join(f"- {name}: {desc}" for name, desc in dimensions.items())
    constraints, body = (None, None)
    from .prompts import build_prompt

    constraints, body = build_prompt(
        "evaluator.rubric.md",
        {
            "concepto": concept_name,
            "rubric_dimensions": dimensions_text,
            "respuesta": response,
        },
    )

    model_scores = []
    panel_models = config.get("panel", {}).get("evaluator_models", [])
    if not panel_models:
        # fallback to evaluador role model marker not available; evaluation cannot run
        panel_models = []

    for model_name in panel_models:
        output = infer("evaluador", body, constraints)
        try:
            parsed = _extract_json(output)
        except (json.JSONDecodeError, ValueError):
            parsed = {}
        cleaned = {}
        for dimension in dimensions:
            try:
                cleaned[dimension] = float(parsed.get(dimension, 0.0))
            except (TypeError, ValueError):
                cleaned[dimension] = 0.0
        model_scores.append(cleaned)

    if not model_scores:
        median_scores = {dimension: 0.0 for dimension in dimensions}
        variance = 0.0
    else:
        median_scores = {}
        variances = {}
        for dimension in dimensions:
            values = [score.get(dimension, 0.0) for score in model_scores]
            median_scores[dimension] = float(statistics.median(values)) if values else 0.0
            if len(values) > 1:
                variances[dimension] = statistics.pvariance(values)
            else:
                variances[dimension] = 0.0
        variance = max(variances.values()) if variances else 0.0

    aggregate = sum(median_scores.values()) / len(median_scores) if median_scores else 0.0

    thresholds = config.get("thresholds", {})
    aggregate_threshold = float(thresholds.get("aggregate", 0.75))
    dimension_floor = float(thresholds.get("dimension_floor", 0.5))
    variance_max = float(thresholds.get("variance_max", 0.3))

    flagged = variance > variance_max
    passed = (
        aggregate >= aggregate_threshold
        and all(score >= dimension_floor for score in median_scores.values())
        and variance <= variance_max
    )
    if flagged:
        passed = False

    rationale = f"Evaluated by {len(panel_models)} model(s)."
    if flagged:
        rationale += " Flagged for high variance."

    return {
        "scores": median_scores,
        "aggregate": aggregate,
        "variance": variance,
        "flagged": flagged,
        "passed": passed,
        "rationale": rationale,
    }

