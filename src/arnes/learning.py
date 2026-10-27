"""Learning service independent of the terminal.

Only durable states are persisted. An attempt, its scores, and the resulting
progress are committed together after evaluation completes successfully.
"""

from .config import load_config, require_ready
from .errors import ArnesError
from .evaluator import evaluate
from .orchestrator import State, after_evaluation
from .planner import load_plan
from .prompts import request_prompt
from .provider import infer
from .sources import for_concept, load_sources
from .store import append_log, load_session, load_state, now, save_state
from .validator import json_object, require_text, validated_text


class LearningSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        load_session(session_id)

    def state(self) -> dict:
        return load_state(self.session_id)

    def _ready(self) -> tuple[dict, dict, dict]:
        session = load_session(self.session_id)
        if not session["locked"]:
            raise ArnesError("Primero revisá /plan y aceptalo con /accept.")
        plan = load_plan(self.session_id)
        state = self.state()
        try:
            State(state["current_state"])
            index = state["current_concept_index"]
            if (
                not plan["concepts"]
                or type(index) is not int
                or not 0 <= index <= len(plan["concepts"])
            ):
                raise ValueError("Invalid concept index")
            if (index == len(plan["concepts"])) != (state["current_state"] == State.DONE):
                raise ValueError("Invalid completion state")
            if state["current_state"] == State.FREE_MODE and state["state_before_free"] not in (
                State.DIAGNOSE,
                State.PRESENT,
                State.AWAIT_ATTEMPT,
            ):
                raise ValueError("Invalid previous state")
            if (
                state["current_state"] == State.AWAIT_ATTEMPT
                or state["state_before_free"] == State.AWAIT_ATTEMPT
            ):
                exercise = state["exercise"]
                if not isinstance(exercise, dict) or not all(
                    isinstance(exercise.get(key), str) and exercise[key].strip()
                    for key in ("explanation", "question")
                ):
                    raise ValueError("Invalid exercise")
        except (KeyError, ValueError, TypeError) as exc:
            raise ArnesError(
                "El estado de la sesión es inconsistente. Revisá state.json antes de continuar."
            ) from exc
        return session, plan, state

    def _context(self, session: dict, plan: dict, state: dict) -> dict:
        concept = plan["concepts"][state["current_concept_index"]]
        recent = [
            attempt for attempt in state["attempts"] if attempt["concept_id"] == concept["id"]
        ][-3:]
        return {
            "goal": session["goal"],
            "concept": concept,
            "rubric": plan["rubric"],
            "sources": for_concept(load_sources(self.session_id), concept),
            "diagnostic": state["diagnostic"],
            "exercise": state["exercise"],
            "recent_attempts": [
                {
                    "question": item["exercise"]["question"],
                    "response": item["response"],
                    "scores": item["scores"],
                    "feedback": item["feedback"],
                    "inconclusive": item["flagged"],
                }
                for item in recent
            ],
        }

    def view(self) -> str:
        session = load_session(self.session_id)
        if not session["locked"]:
            return "Plan pendiente de aceptación. Usá /plan, /plan generar o /accept."
        _, plan, state = self._ready()
        status = State(state["current_state"])
        if status == State.DIAGNOSE:
            return f"Objetivo: {session['goal']}\n\nAntes de empezar, ¿qué sabés del tema y qué te cuesta? Podés responder 'no sé'. Este diagnóstico no lleva nota."
        if status == State.DONE:
            return self.summary()
        if status == State.FREE_MODE:
            return "Modo libre. Escribí 'volver' para retomar el mismo ejercicio."
        if status == State.PRESENT:
            return "Hay un concepto pendiente de presentar. Usá /continue."
        exercise = state["exercise"]
        concept = plan["concepts"][state["current_concept_index"]]
        return f"## {concept['title']}\n\n{exercise['explanation']}\n\n**Tu turno:** {exercise['question']}"

    def present(self) -> str:
        session, plan, state = self._ready()
        if state["current_state"] != State.PRESENT:
            return self.view()
        config = load_config()
        require_ready(config)
        context = self._context(session, plan, state)
        constraints, body, system = request_prompt("tutor.exercise.md", context)
        result = json_object(
            validated_text(
                infer("tutor", body, constraints, system=system, config=config), constraints
            )
        )
        exercise = {
            "explanation": require_text(result.get("explanation"), "Explicación", maximum=8000),
            "question": require_text(result.get("question"), "Pregunta", maximum=4000),
            "hints": [],
        }
        state.update(exercise=exercise, current_state=State.AWAIT_ATTEMPT.value)
        save_state(self.session_id, state)
        append_log("exercise_presented", self.session_id, {"concept_id": context["concept"]["id"]})
        return self.view()

    def respond(self, text: str) -> str:
        text = require_text(text, "Respuesta", maximum=8000)
        session, plan, state = self._ready()
        status = State(state["current_state"])
        if status == State.DONE:
            return self.summary()
        if status == State.FREE_MODE:
            if text.casefold() == "volver":
                state["current_state"] = state["state_before_free"]
                state.update(state_before_free=None, free_history=[])
                save_state(self.session_id, state)
                return "Volviendo al plan.\n\n" + self.view()
            return self._free_response(text, session, plan, state)
        if text.casefold() == "libre":
            state.update(
                state_before_free=status.value, current_state=State.FREE_MODE.value, free_history=[]
            )
            save_state(self.session_id, state)
            return self.view()
        if text.casefold() == "pista":
            return self.hint()
        if status == State.DIAGNOSE:
            state.update(diagnostic=text, current_state=State.PRESENT.value)
            save_state(self.session_id, state)
            return "Diagnóstico guardado. Vamos a practicar el primer concepto."
        if status != State.AWAIT_ATTEMPT:
            raise ArnesError("Primero pedí el próximo ejercicio con /continue.")

        config = load_config()
        context = self._context(session, plan, state)
        # Provider and validation failures must not modify progress.
        result = evaluate(text, plan["rubric"], context, config)
        next_state, index = after_evaluation(
            result, state["current_concept_index"], len(plan["concepts"])
        )
        attempt = {
            "turn": state["total_attempts"] + 1,
            "timestamp": now(),
            "concept_id": context["concept"]["id"],
            "concept": context["concept"]["title"],
            "exercise": state["exercise"],
            "response": text,
            **result,
        }
        state["attempts"].append(attempt)
        state.update(
            total_attempts=attempt["turn"],
            current_state=next_state.value,
            current_concept_index=index,
            exercise=None,
            last_feedback=result["feedback"],
        )
        save_state(self.session_id, state)
        append_log(
            "evaluation_done",
            self.session_id,
            {"turn": attempt["turn"], "passed": result["passed"], "flagged": result["flagged"]},
        )
        if result["flagged"]:
            outcome = "Evaluación inconclusa: los evaluadores discrepan. Vamos a comprobarlo con otro ejercicio."
        elif result["passed"]:
            outcome = "Objetivo del concepto alcanzado."
        else:
            outcome = "Vamos a reforzar este concepto con otro enfoque."
        scores = ""
        if config["ui"]["show_scores"]:
            scores = "\n\nPuntajes: " + ", ".join(
                f"{plan['rubric'][name]['label']}: {value:.2f}"
                for name, value in result["scores"].items()
            )
            scores += f". Agregado: {result['aggregate']:.2f}; varianza: {result['variance']:.3f}."
        return f"{outcome}\n\n{result['feedback']}{scores}" + (
            "\n\n" + self.summary() if next_state == State.DONE else ""
        )

    def hint(self) -> str:
        session, plan, state = self._ready()
        if state["current_state"] != State.AWAIT_ATTEMPT:
            raise ArnesError("Las pistas están disponibles cuando hay un ejercicio pendiente.")
        hints = state["exercise"]["hints"]
        if len(hints) >= 5:
            return "Ya tenés cinco pistas para este ejercicio. Probá responder con lo que entendiste; el feedback te ayudará a seguir."
        config = load_config()
        require_ready(config)
        constraints, body, system = request_prompt(
            "tutor.hint.md", self._context(session, plan, state)
        )
        output = validated_text(
            infer("tutor", body, constraints, system=system, config=config), constraints
        )
        state["exercise"]["hints"] = hints + [output]
        save_state(self.session_id, state)
        return output

    def _free_response(self, text: str, session: dict, plan: dict, state: dict) -> str:
        config = load_config()
        require_ready(config)
        context = self._context(session, plan, state)
        context.update(message=text, history=state["free_history"][-6:])
        constraints, body, system = request_prompt("tutor.free.md", context)
        output = validated_text(
            infer("tutor", body, constraints, system=system, config=config), constraints
        )
        state["free_history"] = (
            context["history"]
            + [{"role": "user", "content": text}, {"role": "assistant", "content": output}]
        )[-6:]
        save_state(self.session_id, state)
        return output

    def summary(self) -> str:
        _, plan, state = self._ready()
        index = state["current_concept_index"]
        heading = (
            "Plan completado. ¡Buen trabajo!"
            if state["current_state"] == State.DONE
            else "Progreso"
        )
        lines = [
            f"## {heading}",
            f"Conceptos superados: {index}/{len(plan['concepts'])}. Intentos: {state['total_attempts']}.",
        ]
        for concept in plan["concepts"][:index]:
            lines.append(f"- {concept['title']}: {concept['objective']}")
        if state["current_state"] == State.DONE:
            lines.append(
                "\nEsto registra desempeño en estos ejercicios, no una certificación. Practicá también sin ayuda. Usá /new para otro objetivo."
            )
        else:
            lines.append(f"\nConcepto actual: {plan['concepts'][index]['title']}.")
        return "\n".join(lines)
