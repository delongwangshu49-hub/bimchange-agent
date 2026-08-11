"""Provider-neutral explanation boundary with DeepSeek enabled for preview use."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit


ProviderStatus = Literal["enabled", "coming_soon"]
MAX_EXPLANATION_CHANGES = 200
MAX_PROVIDER_RESPONSE_BYTES = 2 * 1024 * 1024


class ProviderConfigurationError(ValueError):
    """Raised for unavailable or incomplete provider configuration."""


class ProviderRequestError(RuntimeError):
    """Raised when a provider request fails or returns an invalid response."""


@dataclass(frozen=True)
class ProviderDescriptor:
    provider_id: str
    display_name: str
    status: ProviderStatus
    status_message_zh: str
    default_base_url: str | None = None
    default_model: str | None = None
    api_key_environment: str | None = None


@dataclass(frozen=True)
class ProviderSettings:
    provider_id: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"


class ExplanationProvider(Protocol):
    """Interface implemented by future report explanation providers."""

    def explain(
        self,
        artifact: dict[str, Any],
        *,
        api_key: str,
        timeout_seconds: float = 60.0,
    ) -> dict[str, Any]: ...


PROVIDER_CATALOG = (
    ProviderDescriptor(
        provider_id="deepseek",
        display_name="DeepSeek",
        status="enabled",
        status_message_zh="首版可用",
        default_base_url="https://api.deepseek.com",
        default_model="deepseek-v4-flash",
        api_key_environment="DEEPSEEK_API_KEY",
    ),
    ProviderDescriptor(
        provider_id="openai",
        display_name="OpenAI",
        status="coming_soon",
        status_message_zh="敬请期待，将在后续更新中支持",
    ),
    ProviderDescriptor(
        provider_id="anthropic",
        display_name="Anthropic",
        status="coming_soon",
        status_message_zh="敬请期待，将在后续更新中支持",
    ),
    ProviderDescriptor(
        provider_id="google",
        display_name="Google Gemini",
        status="coming_soon",
        status_message_zh="敬请期待，将在后续更新中支持",
    ),
)


def provider_catalog() -> tuple[ProviderDescriptor, ...]:
    """Return immutable provider metadata for a future settings UI."""
    return PROVIDER_CATALOG


def require_enabled_provider(provider_id: str) -> ProviderDescriptor:
    """Return an enabled provider or fail without silently falling back."""
    descriptor = next(
        (item for item in PROVIDER_CATALOG if item.provider_id == provider_id), None
    )
    if descriptor is None:
        raise ProviderConfigurationError(f"Unknown AI provider: {provider_id}")
    if descriptor.status != "enabled":
        raise ProviderConfigurationError(
            f"{descriptor.display_name}: {descriptor.status_message_zh}"
        )
    return descriptor


def explanation_input(artifact: dict[str, Any]) -> dict[str, Any]:
    """Remove local-only details and cap records before any optional API call."""
    changes = artifact.get("changes", [])
    selected = changes[:MAX_EXPLANATION_CHANGES]
    return {
        "schema_version": artifact.get("schema_version"),
        "model_pair": {"source": "old_version", "revised": "new_version"},
        "summary": artifact.get("summary", {}),
        "warnings": artifact.get("warnings", []),
        "changes": selected,
        "omitted_change_count": max(0, len(changes) - len(selected)),
    }


class DeepSeekExplanationProvider:
    """Minimal DeepSeek Chat Completions adapter; construction makes no request."""

    def __init__(self, settings: ProviderSettings = ProviderSettings()) -> None:
        require_enabled_provider(settings.provider_id)
        parsed_url = urlsplit(settings.base_url)
        if parsed_url.scheme.lower() != "https" or not parsed_url.hostname:
            raise ProviderConfigurationError(
                "DeepSeek base_url must be an absolute HTTPS URL"
            )
        if parsed_url.username or parsed_url.password:
            raise ProviderConfigurationError(
                "DeepSeek base_url must not contain embedded credentials"
            )
        if parsed_url.query or parsed_url.fragment:
            raise ProviderConfigurationError(
                "DeepSeek base_url must not contain a query string or fragment"
            )
        if not settings.model.strip():
            raise ProviderConfigurationError("DeepSeek model must not be empty")
        self.settings = settings

    def build_request(self, artifact: dict[str, Any]) -> dict[str, Any]:
        """Build the bounded JSON-mode request body without including credentials."""
        payload = explanation_input(artifact)
        return {
            "model": self.settings.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You explain deterministic IFC change records for non-technical "
                        "reviewers. Return one JSON object with keys summary, key_changes, "
                        "and limitations. Never add changes, safety conclusions, or facts "
                        "that are absent from the supplied JSON evidence."
                    ),
                },
                {
                    "role": "user",
                    "content": "Explain this JSON evidence:\n"
                    + json.dumps(payload, ensure_ascii=False),
                },
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 4_000,
            "stream": False,
        }

    def explain(
        self,
        artifact: dict[str, Any],
        *,
        api_key: str,
        timeout_seconds: float = 60.0,
    ) -> dict[str, Any]:
        """Call DeepSeek only when the application explicitly invokes this method."""
        if not api_key.strip():
            raise ProviderConfigurationError("DeepSeek API key must not be empty")
        body = json.dumps(self.build_request(artifact)).encode("utf-8")
        request = urllib.request.Request(
            self.settings.base_url.rstrip("/") + "/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=timeout_seconds
            ) as response:
                response_body = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
                if len(response_body) > MAX_PROVIDER_RESPONSE_BYTES:
                    raise ProviderRequestError("DeepSeek response exceeded the size limit")
                raw = json.loads(response_body.decode("utf-8"))
        except ProviderRequestError:
            raise
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise ProviderRequestError("DeepSeek request failed") from error
        try:
            content = raw["choices"][0]["message"]["content"]
            explanation = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise ProviderRequestError(
                "DeepSeek returned an invalid JSON explanation"
            ) from error
        if not isinstance(explanation, dict):
            raise ProviderRequestError("DeepSeek explanation is not a JSON object")
        if not isinstance(explanation.get("summary"), str):
            raise ProviderRequestError("DeepSeek explanation summary is invalid")
        if not isinstance(explanation.get("key_changes"), list):
            raise ProviderRequestError("DeepSeek explanation key_changes is invalid")
        if not isinstance(explanation.get("limitations"), list):
            raise ProviderRequestError("DeepSeek explanation limitations is invalid")
        return {
            "provider": "deepseek",
            "model": raw.get("model", self.settings.model),
            "explanation": explanation,
            "usage": raw.get("usage"),
        }
