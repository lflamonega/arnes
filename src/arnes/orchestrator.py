"""Pure progression decisions; learning.py handles APIs and persistence."""

import enum


class State(str, enum.Enum):
    DIAGNOSE = "DIAGNOSE"
    PRESENT = "PRESENT"
    AWAIT_ATTEMPT = "AWAIT_ATTEMPT"
    FREE_MODE = "FREE_MODE"
    DONE = "DONE"


def after_evaluation(result: dict, index: int, concept_count: int) -> tuple[State, int]:
    if concept_count <= 0 or not 0 <= index < concept_count:
        raise ValueError("Invalid concept index")
    if result["passed"] and not result["flagged"]:
        index += 1
    return (State.DONE if index == concept_count else State.PRESENT), index
