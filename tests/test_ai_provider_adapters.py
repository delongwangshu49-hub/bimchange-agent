"""Offline contract tests for every optional AI provider adapter."""

from __future__ import annotations

import json
import unittest
import urllib.error
from unittest.mock import patch

from bimchange_agent.ai_providers import (
    AnthropicExplanationProvider,
    DeepSeekExplanationProvider,
    GoogleExplanationProvider,
    OpenAIExplanationProvider,
    ProviderConfigurationError,
    ProviderRequestError,
    ProviderSettings,
    create_explanation_provider,
    default_provider_settings,
    explanation_input,
    provider_catalog,
)


ARTIFACT = {
    "schema_version": "0.2.0-preview.1",
    "source": {"file_name": "private-old.ifc", "absolute_path": "C:/private"},
    "revised": {"file_name": "private-new.ifc"},
    "summary": {"total_supported": 1},
    "warnings": [],
    "changes": [
        {
            "change_type": "added",
            "entity_type": "IfcBeam",
            "global_id": "SYNTHETIC-001",
        }
    ],
}

EXPLANATION = {
    "summary": "One supported change.",
    "key_changes": ["A beam was added."],
    "rational_analysis": "Review the added beam before lower-priority metadata changes.",
    "limitations": ["Review the source model."],
}

CANDIDATE_GEOMETRY_ARTIFACT = {
    "schema_version": "0.3.0-preview.1-candidate",
    "source": {
        "file_name": "redacted-geometry-old.ifc",
        "absolute_path": "__LOCAL_ONLY__/redacted-geometry-old.ifc",
    },
    "revised": {"file_name": "redacted-geometry-new.ifc"},
    "summary": {"total_supported": 1, "geometry_modified": 1},
    "warnings": [],
    "changes": [
        {
            "change_type": "geometry_modified",
            "entity_type": "IfcWall",
            "global_id": "SYNTHETIC-GEOMETRY-001",
            "field": None,
            "geometry_change": {
                "subtype": "placement_translation",
                "delta": [0.25, 0.0, 0.0],
                "distance": 0.25,
                "length_unit": "m",
            },
            "evidence": {
                "selector": "changed.SYNTHETIC-GEOMETRY-001.geometry_changed"
            },
        }
    ],
}


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        return self.payload


class ProviderAdapterTests(unittest.TestCase):
    def test_catalog_exposes_four_enabled_providers_with_defaults(self) -> None:
        self.assertEqual(
            [item.provider_id for item in provider_catalog() if item.status == "enabled"],
            ["deepseek", "openai", "anthropic", "google"],
        )
        for provider_id in ("deepseek", "openai", "anthropic", "google"):
            settings = default_provider_settings(provider_id)
            self.assertTrue(settings.base_url.startswith("https://"))
            self.assertTrue(settings.model)

    def test_builders_are_bounded_and_never_include_credentials_or_file_names(self) -> None:
        providers = (
            DeepSeekExplanationProvider(),
            OpenAIExplanationProvider(),
            AnthropicExplanationProvider(),
            GoogleExplanationProvider(),
        )
        for provider in providers:
            with self.subTest(provider=provider.provider_id):
                body = provider.build_request(ARTIFACT)
                serialized = json.dumps(body)
                self.assertNotIn("API-KEY-ONLY-IN-HEADER", serialized)
                self.assertNotIn("private-old.ifc", serialized)
                self.assertNotIn("private-new.ifc", serialized)
                self.assertNotIn("C:/private", serialized)
                request = provider.build_http_request(
                    ARTIFACT, api_key="API-KEY-ONLY-IN-HEADER"
                )
                self.assertNotIn(b"API-KEY-ONLY-IN-HEADER", request.data or b"")
                headers = {key.lower(): value for key, value in request.header_items()}
                self.assertTrue(
                    "authorization" in headers
                    or "x-api-key" in headers
                    or "x-goog-api-key" in headers
                )

    def test_candidate_geometry_explanation_input_keeps_semantics_not_paths(self) -> None:
        bounded = explanation_input(CANDIDATE_GEOMETRY_ARTIFACT)
        serialized = json.dumps(bounded, ensure_ascii=False)
        self.assertIn("placement_translation", serialized)
        self.assertIn("SYNTHETIC-GEOMETRY-001", serialized)
        self.assertNotIn("redacted-geometry-old.ifc", serialized)
        self.assertNotIn("redacted-geometry-new.ifc", serialized)
        self.assertNotIn("__LOCAL_ONLY__", serialized)
        for provider in (
            DeepSeekExplanationProvider(),
            OpenAIExplanationProvider(),
            AnthropicExplanationProvider(),
            GoogleExplanationProvider(),
        ):
            with self.subTest(provider=provider.provider_id):
                request = json.dumps(
                    provider.build_request(CANDIDATE_GEOMETRY_ARTIFACT),
                    ensure_ascii=False,
                )
                self.assertIn("placement_translation", request)
                self.assertNotIn("redacted-geometry-old.ifc", request)
                self.assertNotIn("__LOCAL_ONLY__", request)

    def test_request_shapes_follow_each_provider_protocol(self) -> None:
        deepseek = DeepSeekExplanationProvider().build_request(ARTIFACT)
        self.assertEqual(deepseek["response_format"], {"type": "json_object"})
        self.assertEqual(deepseek["thinking"], {"type": "disabled"})

        openai = OpenAIExplanationProvider().build_request(ARTIFACT)
        self.assertFalse(openai["store"])
        self.assertEqual(openai["text"]["format"]["type"], "json_schema")
        self.assertTrue(openai["text"]["format"]["strict"])

        anthropic_provider = AnthropicExplanationProvider()
        anthropic = anthropic_provider.build_request(ARTIFACT)
        self.assertEqual(
            anthropic["output_config"]["format"]["type"], "json_schema"
        )
        headers = {
            key.lower(): value
            for key, value in anthropic_provider.build_http_request(
                ARTIFACT, api_key="test-key"
            ).header_items()
        }
        self.assertEqual(headers["anthropic-version"], "2023-06-01")

        google = GoogleExplanationProvider().build_request(ARTIFACT)
        response_format = google["generationConfig"]["responseFormat"]["text"]
        self.assertEqual(response_format["mimeType"], "application/json")
        self.assertEqual(response_format["schema"]["type"], "object")

    def test_output_language_and_rational_analysis_are_explicit(self) -> None:
        provider = OpenAIExplanationProvider()
        chinese = json.dumps(
            provider.build_request(ARTIFACT, language="zh_CN"), ensure_ascii=False
        )
        english = json.dumps(provider.build_request(ARTIFACT, language="en"))
        self.assertIn("Simplified Chinese", chinese)
        self.assertIn("English", english)
        schema = provider.build_request(ARTIFACT)["text"]["format"]["schema"]
        self.assertIn("rational_analysis", schema["required"])

    def test_each_adapter_parses_its_offline_response_fixture(self) -> None:
        fixtures = (
            (
                DeepSeekExplanationProvider(),
                {
                    "model": "deepseek-v4-flash",
                    "choices": [{"message": {"content": json.dumps(EXPLANATION)}}],
                    "usage": {"total_tokens": 10},
                },
            ),
            (
                OpenAIExplanationProvider(),
                {
                    "model": "gpt-5.6-luna",
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {"type": "output_text", "text": json.dumps(EXPLANATION)}
                            ],
                        }
                    ],
                    "usage": {"total_tokens": 10},
                },
            ),
            (
                AnthropicExplanationProvider(),
                {
                    "model": "claude-sonnet-4-6",
                    "content": [{"type": "text", "text": json.dumps(EXPLANATION)}],
                    "usage": {"input_tokens": 5, "output_tokens": 5},
                },
            ),
            (
                GoogleExplanationProvider(),
                {
                    "candidates": [
                        {"content": {"parts": [{"text": json.dumps(EXPLANATION)}]}}
                    ],
                    "usageMetadata": {"totalTokenCount": 10},
                },
            ),
        )
        for provider, fixture in fixtures:
            with self.subTest(provider=provider.provider_id):
                with patch(
                    "bimchange_agent.ai_providers.urllib.request.urlopen",
                    return_value=_Response(fixture),
                ) as urlopen:
                    result = provider.explain(ARTIFACT, api_key="offline-test-key")
                self.assertEqual(result["provider"], provider.provider_id)
                self.assertEqual(result["explanation"], EXPLANATION)
                urlopen.assert_called_once()

    def test_deepseek_accepts_fenced_json_and_fills_optional_analysis_fields(self) -> None:
        partial = {
            "summary": "发现一项受支持的变更。",
            "key_changes": ["新增一根梁。"],
        }
        fixture = {
            "model": "deepseek-v4-flash",
            "choices": [
                {
                    "message": {
                        "content": "```json\n"
                        + json.dumps(partial, ensure_ascii=False)
                        + "\n```"
                    }
                }
            ],
            "usage": {"total_tokens": 10},
        }
        provider = DeepSeekExplanationProvider()
        with patch(
            "bimchange_agent.ai_providers.urllib.request.urlopen",
            return_value=_Response(fixture),
        ):
            result = provider.explain(
                ARTIFACT,
                api_key="offline-test-key",
                language="zh_CN",
            )
        explanation = result["explanation"]
        self.assertIn("优先逐项核对", explanation["rational_analysis"])
        self.assertEqual(explanation["limitations"], [])

    def test_factory_rejects_cross_provider_settings_and_network_errors_are_generic(self) -> None:
        with self.assertRaises(ProviderConfigurationError):
            OpenAIExplanationProvider(ProviderSettings())
        provider = create_explanation_provider(default_provider_settings("openai"))
        with patch(
            "bimchange_agent.ai_providers.urllib.request.urlopen",
            side_effect=urllib.error.URLError("offline"),
        ):
            with self.assertRaisesRegex(ProviderRequestError, "Could not reach OpenAI"):
                provider.explain(ARTIFACT, api_key="offline-test-key")

    def test_http_authentication_error_is_classified_without_response_body(self) -> None:
        provider = OpenAIExplanationProvider()
        error = urllib.error.HTTPError(
            provider.build_http_request(
                ARTIFACT, api_key="offline-test-key"
            ).full_url,
            401,
            "Unauthorized",
            hdrs=None,
            fp=None,
        )
        with patch(
            "bimchange_agent.ai_providers.urllib.request.urlopen",
            side_effect=error,
        ):
            with self.assertRaises(ProviderRequestError) as raised:
                provider.explain(ARTIFACT, api_key="offline-test-key")
        self.assertEqual(raised.exception.category, "authentication")
        self.assertEqual(raised.exception.status_code, 401)
        self.assertNotIn("offline-test-key", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
