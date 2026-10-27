import statistics

from .config import evaluator_specs, require_ready
from .errors import ValidationError
from .prompts import request_prompt
from .provider import infer
from .validator import json_object, require_text, score_number, validated_text


def evaluate(response: str, rubric: dict, concept: dict, config: dict) -> dict:
    """Treat an incomplete or invalid panel as a technical error, never a zero score."""
    require_ready(config)
    dimensions = rubric
    if not isinstance(dimensions, dict) or not dimensions:
        raise ValidationError("No hay dimensiones de evaluación.")
    # Withhold prior grades and self-assessments to reduce anchoring bias.
    context = {
        key: concept[key] for key in ("goal", "concept", "exercise", "sources") if key in concept
    }
    context.update(rubric=dimensions, response=response)
    constraints, body, system = request_prompt("evaluator.score.md", context, role="evaluator")
    evaluations = []
    for spec in evaluator_specs(config):
        output = infer(
            "evaluator",
            body,
            constraints,
            system=system,
            model=spec["model"],
            provider_name=spec["provider"],
            config=config,
        )
        parsed = json_object(validated_text(output, constraints))
        scores = parsed.get("scores")
        if not isinstance(scores, dict) or set(scores) != set(dimensions):
            raise ValidationError(
                "El evaluador no devolvió exactamente las dimensiones de la rúbrica. El intento no se calificó."
            )
        cleaned = {name: score_number(scores[name], name) for name in dimensions}
        feedback = require_text(parsed.get("feedback"), "Feedback del evaluador", maximum=8000)
        evaluations.append({**spec, "scores": cleaned, "feedback": feedback})

    medians = {
        name: float(statistics.median(item["scores"][name] for item in evaluations))
        for name in dimensions
    }
    variances = {
        name: statistics.pvariance(item["scores"][name] for item in evaluations)
        for name in dimensions
    }
    variance = max(variances.values())
    aggregate = statistics.mean(medians.values())
    thresholds = dict(config["thresholds"])
    flagged = variance > thresholds["variance_max"]
    passed = (
        not flagged
        and aggregate >= thresholds["aggregate"]
        and min(medians.values()) >= thresholds["dimension_floor"]
    )
    feedback = "\n\n".join(dict.fromkeys(item["feedback"] for item in evaluations))
    return {
        "scores": medians,
        "aggregate": aggregate,
        "variance": variance,
        "variances": variances,
        "flagged": flagged,
        "passed": passed,
        "feedback": feedback,
        "evaluations": evaluations,
        "thresholds": thresholds,
    }
