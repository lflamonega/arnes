"""OpenAI-compatible client without implicit history or hidden billable retries."""

import json
import urllib.error
import urllib.request

from .config import load_config, validate_base_url
from .credentials import get_provider
from .errors import ProviderError
from .store import append_log

MAX_RESPONSE_BYTES = 2_000_000


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a bearer token to a redirect target.
        return None


def _request_json(request: urllib.request.Request, timeout: int = 60) -> dict:
    try:
        opener = urllib.request.build_opener(_NoRedirect)
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ProviderError("La respuesta del proveedor excede el límite de 2 MB.")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ProviderError("El proveedor devolvió JSON, pero no un objeto.")
        return data
    except urllib.error.HTTPError as exc:
        # Remote error bodies may expose credentials or request contents.
        messages = {
            401: "Credencial inválida; revisá /connect.",
            403: "El proveedor denegó el acceso.",
            429: "Límite de uso alcanzado; esperá y volvé a intentar.",
        }
        raise ProviderError(
            messages.get(exc.code, f"El proveedor respondió HTTP {exc.code}. Revisá modelo y URL.")
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderError(
            "No se pudo contactar al proveedor. Revisá la conexión y volvé a intentar."
        ) from exc
    except (ValueError, UnicodeError) as exc:
        raise ProviderError("El proveedor devolvió una respuesta JSON inválida.") from exc


class InferenceProvider:
    def complete(self, messages: list[dict], constraints: dict) -> str:
        raise NotImplementedError


class OpenRouterProvider(InferenceProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        *,
        model: str = "",
        temperature: float = 0.7,
    ):
        validate_base_url(base_url)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature

    def complete(self, messages: list[dict], constraints: dict) -> str:
        if not self.model:
            raise ProviderError("No hay modelo configurado para este rol. Usá /settings.")
        payload = {"model": self.model, "messages": messages, "temperature": self.temperature}
        if "max_tokens" in constraints:
            payload["max_tokens"] = int(constraints["max_tokens"])
        if constraints.get("response_format") == "json":
            payload["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, allow_nan=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        data = _request_json(request)
        try:
            choice = data["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ProviderError(
                    "El modelo agotó el límite de salida. Ajustá max_tokens en el prompt y reintentá."
                )
            content = choice["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Empty content")
            return content.strip()
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
            raise ProviderError(
                "El proveedor no devolvió texto utilizable; el intento no fue evaluado."
            ) from exc


def infer(
    role: str,
    prompt: str,
    constraints: dict | None = None,
    *,
    system: str = "",
    model: str | None = None,
    provider_name: str | None = None,
    config: dict | None = None,
) -> str:
    config = config if config is not None else load_config()
    role_config = config.get("roles", {}).get(role, {})
    provider_name = provider_name or role_config.get("provider", "openrouter")
    model = model if model is not None else role_config.get("model", "")
    tutor = config.get("roles", {}).get("tutor", {})
    if (
        role == "evaluator"
        and model
        and (provider_name, model) == (tutor.get("provider"), tutor.get("model"))
    ):
        raise ProviderError("El evaluador no puede ser el mismo modelo que el tutor.")
    info = get_provider(provider_name)
    if not isinstance(info, dict):
        raise ProviderError(f"No hay credenciales para {provider_name}. Usá /connect.")
    provider = OpenRouterProvider(
        info.get("api_key", ""),
        info.get("base_url", "https://openrouter.ai/api/v1"),
        model=model,
        temperature=role_config.get("temperature", 0.0),
    )
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    append_log("model_called", payload={"role": role, "provider": provider_name, "model": model})
    return provider.complete(messages, constraints or {})


def list_models(provider_name: str) -> list[str]:
    info = get_provider(provider_name)
    if not info:
        raise ProviderError(f"No hay credenciales para {provider_name}.")
    base_url = info.get("base_url", "https://openrouter.ai/api/v1")
    validate_base_url(base_url)
    data = _request_json(
        urllib.request.Request(
            base_url.rstrip("/") + "/models",
            headers={"Authorization": f"Bearer {info.get('api_key', '')}"},
        ),
        timeout=30,
    )
    models = data.get("data")
    if not isinstance(models, list):
        raise ProviderError("El proveedor no devolvió una lista válida de modelos.")
    return sorted(
        item["id"] for item in models if isinstance(item, dict) and isinstance(item.get("id"), str)
    )
