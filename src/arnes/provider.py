import json
import urllib.error
import urllib.request

from .config import load_config
from .credentials import get_provider
from .store import append_log


class InferenceProvider:
    def complete(self, messages: list[dict], constraints: dict) -> str:
        raise NotImplementedError


class OpenRouterProvider(InferenceProvider):
    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def complete(self, messages, constraints):
        constraints = constraints or {}
        role = constraints.get("_role", "tutor")
        config = load_config()
        role_config = config.get("roles", {}).get(role, {})
        model = role_config.get("model", "")
        temperature = role_config.get("temperature", 0.7)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if "max_tokens" in constraints:
            try:
                payload["max_tokens"] = int(constraints["max_tokens"])
            except (TypeError, ValueError):
                pass
        if constraints.get("response_format") == "json":
            payload["response_format"] = {"type": "json_object"}

        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(error_body) from exc
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc

        data = json.loads(body)
        return data["choices"][0]["message"]["content"]


def infer(role: str, prompt: str, constraints: dict) -> str:
    config = load_config()
    role_config = config.get("roles", {}).get(role, {})
    provider_name = role_config.get("provider", "openrouter")

    if role == "evaluador":
        tutor_provider = config.get("roles", {}).get("tutor", {}).get("provider")
        tutor_model = config.get("roles", {}).get("tutor", {}).get("model")
        evaluador_model = role_config.get("model")
        if provider_name == tutor_provider and tutor_model and tutor_model == evaluador_model:
            raise RuntimeError("El evaluador no puede ser el mismo modelo que el tutor.")

    info = get_provider(provider_name)
    if not info:
        raise RuntimeError(f"No hay credenciales para el proveedor: {provider_name}")

    messages = [{"role": "user", "content": prompt}]
    provider = OpenRouterProvider(
        api_key=info.get("api_key", ""),
        base_url=info.get("base_url", "https://openrouter.ai/api/v1"),
    )
    constraints = dict(constraints or {})
    constraints["_role"] = role
    append_log("model_called", None, {"role": role, "provider": provider_name})
    return provider.complete(messages, constraints)


def list_models(provider_name: str) -> list[str]:
    info = get_provider(provider_name)
    if not info:
        return []
    base_url = info.get("base_url", "https://openrouter.ai/api/v1").rstrip("/")
    request = urllib.request.Request(
        f"{base_url}/models",
        headers={"Authorization": f"Bearer {info.get('api_key', '')}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []
    models = []
    for item in data.get("data", []):
        model_id = item.get("id")
        if model_id:
            models.append(model_id)
    return sorted(models)
