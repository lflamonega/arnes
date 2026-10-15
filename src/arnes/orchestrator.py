import enum


class State(enum.Enum):
    DIAGNOSE = "DIAGNOSE"
    PRESENT = "PRESENT"
    AWAIT_ATTEMPT = "AWAIT_ATTEMPT"
    EVALUATE = "EVALUATE"
    FEEDBACK = "FEEDBACK"
    ADVANCE = "ADVANCE"
    REMEDIATE = "REMEDIATE"
    FREE_MODE = "FREE_MODE"
    DONE = "DONE"


class Action(enum.Enum):
    ASK_DIAGNOSTIC = "ASK_DIAGNOSTIC"
    PRESENT_CONCEPT = "PRESENT_CONCEPT"
    AWAIT = "AWAIT"
    GIVE_HINT = "GIVE_HINT"
    GIVE_FEEDBACK = "GIVE_FEEDBACK"
    ADVANCE = "ADVANCE"
    REMEDIATE = "REMEDIATE"
    FREE_MODE = "FREE_MODE"
    DONE = "DONE"


def next_action(state: State, context: dict) -> Action:
    mapping = {
        State.DIAGNOSE: Action.ASK_DIAGNOSTIC,
        State.PRESENT: Action.PRESENT_CONCEPT,
        State.AWAIT_ATTEMPT: Action.AWAIT,
        State.EVALUATE: Action.AWAIT,
        State.FEEDBACK: Action.GIVE_FEEDBACK,
        State.ADVANCE: Action.ADVANCE,
        State.REMEDIATE: Action.REMEDIATE,
        State.FREE_MODE: Action.FREE_MODE,
        State.DONE: Action.DONE,
    }
    return mapping.get(state, Action.AWAIT)


def transition(state: State, event: str, evaluation: dict | None = None) -> State:
    event = event or ""
    evaluation = evaluation or {}

    if state == State.DIAGNOSE and event == "response":
        return State.EVALUATE
    if state == State.PRESENT and event == "response":
        return State.EVALUATE
    if state == State.AWAIT_ATTEMPT and event == "response":
        return State.EVALUATE
    if state == State.AWAIT_ATTEMPT and event == "hint":
        return State.FEEDBACK
    if state == State.AWAIT_ATTEMPT and event == "off_topic":
        return State.FREE_MODE

    if state == State.EVALUATE:
        if event in ("pass", "fail", "ambiguous", "response"):
            return State.FEEDBACK
        return state

    if state == State.FEEDBACK:
        passed = evaluation.get("passed", False)
        if event == "pass":
            passed = True
        if event in ("fail", "ambiguous"):
            passed = False
        return State.ADVANCE if passed else State.REMEDIATE

    if state == State.ADVANCE:
        if event in ("", "next", "advance"):
            return State.PRESENT
        return State.PRESENT

    if state == State.REMEDIATE:
        if event in ("", "next", "remediate"):
            return State.PRESENT
        return State.PRESENT

    if state == State.FREE_MODE and event == "free_done":
        previous = evaluation.get("state_before_free", "DIAGNOSE")
        try:
            return State(previous)
        except ValueError:
            return State.DIAGNOSE

    if state == State.DONE:
        return State.DONE

    return state
