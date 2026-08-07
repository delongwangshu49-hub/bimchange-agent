"""Minimal, comparable Gate 3 runners for the three experimental workflows."""

from __future__ import annotations

import http.client
import json
import os
import time
import urllib.error
import urllib.request
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from jsonschema import Draft202012Validator, ValidationError

from .change_query import REQUEST_SCHEMA_PATH, load_json, query_change_records
from .evidence_validation import (
    prediction_fact,
    record_fact,
    validate_candidate_schema,
    validate_evidence,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
QUESTIONS_PATH = REPOSITORY_ROOT / "evals" / "questions" / "gate3-questions.json"
MODEL_SUMMARY_PATH = (
    REPOSITORY_ROOT
    / "evals"
    / "inputs"
    / "development"
    / "gate3-model-pair-summary.json"
)
CANDIDATE_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "candidate-answer.schema.json"
CLAIM_VALIDATION_SCHEMA_PATH = (
    REPOSITORY_ROOT / "schemas" / "claim-validation.schema.json"
)
CHANGE_RECORD_SOURCE = "data/ground_truth/gate2-change-records.json"
MODEL_SUMMARY_SOURCE = "evals/inputs/development/gate3-model-pair-summary.json"
DEEPSEEK_RESPONSES_URL = "https://api.deepseek.com/responses"
VALIDATOR_MAX_OUTPUT_TOKENS = 16000


class BudgetExceeded(RuntimeError):
    """Raised before a request that would exceed the configured cost ceiling."""


class ResponsesClient(Protocol):
    """Small provider boundary used by the Gate 3 orchestration code."""

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create one model response."""


@dataclass(frozen=True)
class RunConfig:
    """Frozen model and experiment parameters shared across workflows."""

    provider: str = "deepseek"
    model: str = "deepseek-v4-flash"
    reasoning_effort: str = "high"
    max_output_tokens: int = 16000
    max_transient_retries: int = 2
    budget_usd: float = 0.5
    input_usd_per_million: float = 0.14
    cached_input_usd_per_million: float = 0.0028
    output_usd_per_million: float = 0.28
    store: bool = False

    def __post_init__(self) -> None:
        if self.provider != "deepseek":
            raise ValueError("The development runner currently supports provider=deepseek")
        if self.model != "deepseek-v4-flash":
            raise ValueError("Development model is locked to deepseek-v4-flash")
        if self.budget_usd <= 0:
            raise ValueError("budget_usd must be positive")


@dataclass
class UsageLedger:
    """Track API calls, tokens, and estimated text-token cost."""

    config: RunConfig
    request_attempts: int = 0
    successful_responses: int = 0
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0

    def projected_request_cost(self, payload: dict[str, Any]) -> float:
        """Conservatively estimate one request before it is sent."""
        estimated_input = max(1, len(json.dumps(payload, ensure_ascii=False)) // 4)
        output_limit = int(
            payload.get("max_output_tokens", self.config.max_output_tokens)
        )
        return (
            estimated_input * self.config.input_usd_per_million
            + output_limit * self.config.output_usd_per_million
        ) / 1_000_000

    def ensure_budget(self, payload: dict[str, Any]) -> None:
        """Stop before a request whose conservative projection crosses the ceiling."""
        projected = self.estimated_cost_usd + self.projected_request_cost(payload)
        if projected > self.config.budget_usd:
            raise BudgetExceeded(
                f"Projected cost ${projected:.4f} exceeds the "
                f"${self.config.budget_usd:.2f} ceiling"
            )

    def record(self, response: dict[str, Any]) -> None:
        """Record safe usage metadata from a successful response."""
        usage = response.get("usage") or {}
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
        details = usage.get("input_tokens_details") or {}
        cached_tokens = int(details.get("cached_tokens", 0))
        uncached_tokens = max(0, input_tokens - cached_tokens)
        cost = (
            uncached_tokens * self.config.input_usd_per_million
            + cached_tokens * self.config.cached_input_usd_per_million
            + output_tokens * self.config.output_usd_per_million
        ) / 1_000_000
        self.successful_responses += 1
        self.input_tokens += input_tokens
        self.cached_input_tokens += cached_tokens
        self.output_tokens += output_tokens
        self.estimated_cost_usd += cost
        if self.estimated_cost_usd > self.config.budget_usd:
            raise BudgetExceeded(
                f"Actual estimated cost ${self.estimated_cost_usd:.4f} exceeded "
                f"the ${self.config.budget_usd:.2f} ceiling; run stopped"
            )

    def public_summary(self) -> dict[str, Any]:
        """Return metadata that is safe to store in experiment artifacts."""
        return {
            "request_attempts": self.request_attempts,
            "successful_responses": self.successful_responses,
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "budget_usd": self.config.budget_usd,
        }


class DeepSeekResponsesClient:
    """Dependency-free client for DeepSeek's Responses-compatible API."""

    def __init__(self, config: RunConfig, *, api_key: str | None = None) -> None:
        self.config = config
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not available in the environment")
        self.ledger = UsageLedger(config)

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_payload = {
            "model": self.config.model,
            "reasoning": {"effort": self.config.reasoning_effort},
            "max_output_tokens": self.config.max_output_tokens,
            "store": self.config.store,
            **payload,
        }
        if "text" in request_payload:
            existing_instructions = request_payload.get("instructions", "")
            request_payload["instructions"] = (
                existing_instructions
                + " Return exactly one JSON object and no text or additional JSON "
                "before or after it."
            ).strip()
        self.ledger.ensure_budget(request_payload)
        body = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            DEEPSEEK_RESPONSES_URL,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        for attempt in range(self.config.max_transient_retries + 1):
            self.ledger.request_attempts += 1
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    result = json.loads(response.read().decode("utf-8"))
                if not isinstance(result, dict):
                    raise RuntimeError("DeepSeek Responses API returned a non-object")
                self.ledger.record(result)
                if "text" in request_payload:
                    has_output_text = any(
                        content.get("type") == "output_text"
                        and isinstance(content.get("text"), str)
                        and content["text"].strip()
                        for item in result.get("output", [])
                        if item.get("type") == "message"
                        for content in item.get("content", [])
                    )
                    if not has_output_text and attempt < self.config.max_transient_retries:
                        self.ledger.ensure_budget(request_payload)
                        time.sleep(0.5 * (2**attempt))
                        continue
                return result
            except urllib.error.HTTPError as exc:
                transient = exc.code == 429 or 500 <= exc.code < 600
                if not transient or attempt >= self.config.max_transient_retries:
                    detail = ""
                    try:
                        error_body = json.loads(exc.read().decode("utf-8"))
                        error = error_body.get("error") or {}
                        safe_fields = {
                            key: error.get(key)
                            for key in ("type", "code", "param", "message")
                            if error.get(key) is not None
                        }
                        detail = ": " + json.dumps(
                            safe_fields, ensure_ascii=False
                        )[:1000]
                    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                        pass
                    raise RuntimeError(
                        f"DeepSeek Responses API request failed with status {exc.code}{detail}"
                    ) from None
            except (
                urllib.error.URLError,
                TimeoutError,
                ConnectionError,
                http.client.IncompleteRead,
            ):
                if attempt >= self.config.max_transient_retries:
                    raise RuntimeError("DeepSeek Responses API network request failed") from None
            time.sleep(0.5 * (2**attempt))
        raise AssertionError("unreachable")


@dataclass
class WorkflowRun:
    """One candidate artifact plus safe execution metadata."""

    candidate: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


def response_text(response: dict[str, Any]) -> str:
    """Extract the final output_text item from a Responses API response."""
    texts = [
        content["text"]
        for item in response.get("output", [])
        if item.get("type") == "message"
        for content in item.get("content", [])
        if content.get("type") == "output_text" and isinstance(content.get("text"), str)
    ]
    if not texts:
        item_types = [item.get("type") for item in response.get("output", [])]
        raise RuntimeError(
            "Response did not contain output_text; "
            f"status={response.get('status')}, output_types={item_types}"
        )
    return "".join(texts)


def response_json(response: dict[str, Any]) -> dict[str, Any]:
    """Parse one structured JSON response."""
    data = json.loads(response_text(response))
    if not isinstance(data, dict):
        raise TypeError("Structured model output must be a JSON object")
    return data


def strict_value_schema() -> dict[str, Any]:
    """Represent every value type used by the controlled Gate 2 records."""
    return {
        "anyOf": [
            {"type": "null"},
            {"type": "boolean"},
            {"type": "string"},
            {"type": "number"},
            {
                "type": "object",
                "required": ["name", "tag"],
                "properties": {
                    "name": {"type": ["string", "null"]},
                    "tag": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
        ]
    }


def responses_schema_subset(value: Any) -> Any:
    """Translate local Draft 2020-12 unions to the strict Responses subset."""
    if isinstance(value, list):
        return [responses_schema_subset(item) for item in value]
    if not isinstance(value, dict):
        return value
    translated = {}
    for key, item in value.items():
        translated["anyOf" if key == "oneOf" else key] = responses_schema_subset(item)
    if "type" not in translated and "const" in translated:
        translated["type"] = json_type(translated["const"])
    if "type" not in translated and "enum" in translated:
        enum_types = list(dict.fromkeys(json_type(item) for item in translated["enum"]))
        translated["type"] = enum_types[0] if len(enum_types) == 1 else enum_types
    return translated


def json_type(value: Any) -> str:
    """Return the JSON Schema type name for a Python JSON value."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "array"
    return "object"


def model_answer_schema() -> dict[str, Any]:
    """Build a strict single-answer schema from the common candidate contract."""
    candidate_schema = load_json(CANDIDATE_SCHEMA_PATH)
    defs = responses_schema_subset(deepcopy(candidate_schema["$defs"]))
    defs["prediction"]["properties"]["old_value"] = strict_value_schema()
    defs["prediction"]["properties"]["new_value"] = strict_value_schema()
    schema = {
        "type": "object",
        "required": ["answer"],
        "properties": {"answer": {"$ref": "#/$defs/answer"}},
        "additionalProperties": False,
        "$defs": defs,
    }
    Draft202012Validator.check_schema(schema)
    return schema


def text_format(name: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Return the Responses API strict JSON Schema configuration."""
    return {
        "format": {
            "type": "json_schema",
            "name": name,
            "strict": True,
            "schema": schema,
        },
        "verbosity": "low",
    }


def answer_instructions(workflow: str) -> str:
    """Return common output rules plus workflow-specific evidence rules."""
    evidence_rule = (
        f"Every evidence source_path must equal {MODEL_SUMMARY_SOURCE}; cite it with "
        "source_type=model_pair_summary. Do not copy the nested IFC source paths into "
        "evidence_refs. "
        "Added or deleted items require source and revised presence citations; "
        "property modifications require both version citations."
        if workflow == "direct_llm"
        else f"Cite only returned records from {CHANGE_RECORD_SOURCE} with "
        "source_type=change_query, change_id, and global_id."
    )
    return (
        "Answer only the supplied BIM revision question. Return one schema-valid answer. "
        "Do not invent GUIDs, storeys, fields, values, evidence, safety conclusions, "
        "or unobserved changes. Use status not_found for a supported empty result and "
        "insufficient_evidence when the available source cannot justify the requested "
        "engineering conclusion. Keep the prose answer limited to claims represented by "
        "predictions or explicit limitations. Every prediction object must contain "
        "exactly change_type, entity_type, global_id, location, field, old_value, "
        "new_value, and evidence_refs; never add name, tag, change_id, or any other "
        "top-level prediction field. "
        + evidence_rule
    )


def query_tool() -> dict[str, Any]:
    """Expose the locked deterministic Change Record interface as one strict tool."""
    request_schema = load_json(REQUEST_SCHEMA_PATH)
    filter_properties = responses_schema_subset(
        deepcopy(request_schema["$defs"]["filters"]["properties"])
    )
    for name, property_schema in filter_properties.items():
        filter_properties[name] = {
            "anyOf": [property_schema, {"type": "null"}]
        }
    parameters = {
        "type": "object",
        "required": ["schema_version", "filters"],
        "properties": {
            "schema_version": {"const": "0.1.0"},
            "filters": {
                "type": "object",
                "required": list(filter_properties),
                "properties": filter_properties,
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    }
    return {
        "type": "function",
        "name": "query_change_records",
        "description": (
            "Return verified IFC Change Records matching all supplied filters. "
            "Use an empty filters object to retrieve every verified change."
        ),
        "strict": True,
        "parameters": parameters,
    }


def function_call(response: dict[str, Any]) -> dict[str, Any]:
    """Require exactly one query_change_records call."""
    calls = [item for item in response.get("output", []) if item.get("type") == "function_call"]
    if len(calls) != 1 or calls[0].get("name") != "query_change_records":
        raise RuntimeError("Expected exactly one query_change_records function call")
    return calls[0]


def candidate_for(workflow: str, dataset_id: str, answer: dict[str, Any]) -> dict[str, Any]:
    """Wrap one model answer in the shared candidate artifact."""
    candidate = {
        "schema_version": "0.1.0",
        "dataset_id": dataset_id,
        "question_split": "development",
        "workflow": workflow,
        "answers": [answer],
    }
    validate_candidate_schema(candidate)
    return candidate


def run_direct_question(
    client: ResponsesClient,
    question: dict[str, Any],
    dataset_id: str,
    summary: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run one Direct LLM condition without tool access."""
    response = client.create(
        {
            "instructions": answer_instructions("direct_llm"),
            "input": json.dumps(
                {
                    "question_id": question["question_id"],
                    "question": question["question"],
                    "model_pair_summary": summary,
                },
                ensure_ascii=False,
            ),
            "text": text_format("gate3_direct_answer", model_answer_schema()),
        }
    )
    answer = response_json(response)["answer"]
    if answer["question_id"] != question["question_id"]:
        raise ValueError("Model returned a different question_id")
    candidate_for("direct_llm", dataset_id, answer)
    return answer, {"response_ids": [response.get("id")]}


def call_query_tool(
    client: ResponsesClient, question: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Plan and execute exactly one deterministic Change Record query."""
    planning = client.create(
        {
            "instructions": (
                "Translate the supplied natural-language revision question into exactly "
                "one query_change_records call. Do not answer the question and do not call "
                "any other tool. The question does not include hidden reference filters."
            ),
            "input": json.dumps(
                {
                    "question_id": question["question_id"],
                    "question": question["question"],
                },
                ensure_ascii=False,
            ),
            "tools": [query_tool()],
            "parallel_tool_calls": False,
        }
    )
    call = function_call(planning)
    strict_request = json.loads(call["arguments"])
    if not isinstance(strict_request, dict):
        raise TypeError("Tool arguments must be a JSON object")
    request = {
        "schema_version": strict_request["schema_version"],
        "filters": {
            name: value
            for name, value in strict_request["filters"].items()
            if value is not None
        },
    }
    result = query_change_records(request)
    return planning, call, result


def answer_after_tool(
    client: ResponsesClient,
    workflow: str,
    question: dict[str, Any],
    planning: dict[str, Any],
    call: dict[str, Any],
    tool_result: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate one answer from the model's call and the deterministic result."""
    continuation = [
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question_id": question["question_id"],
                    "question": question["question"],
                },
                ensure_ascii=False,
            ),
        },
        *list(planning.get("output", [])),
        {
            "type": "function_call_output",
            "call_id": call["call_id"],
            "output": json.dumps(tool_result, ensure_ascii=False),
        },
    ]
    response = client.create(
        {
            "instructions": answer_instructions(workflow),
            "input": continuation,
            "text": text_format(f"gate3_{workflow}_answer", model_answer_schema()),
        }
    )
    answer = response_json(response)["answer"]
    if answer["question_id"] != question["question_id"]:
        raise ValueError("Model returned a different question_id")
    return answer, response


def validate_claims(
    client: ResponsesClient,
    question: dict[str, Any],
    answer: dict[str, Any],
    tool_result: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Use an independent call to classify every free-text claim against evidence."""
    schema = load_json(CLAIM_VALIDATION_SCHEMA_PATH)
    schema = responses_schema_subset(
        {
            key: value
            for key, value in schema.items()
            if key not in {"$schema", "$id", "title"}
        }
    )
    response = client.create(
        {
            "instructions": (
                "Act only as an evidence validator. Split the answer and limitations into "
                "atomic factual claims. Classify each as supported, unsupported, or "
                "indeterminate using only the supplied verified Change Records and the "
                "structured predictions. Do not use a reference answer or outside BIM or "
                "engineering knowledge. A statement that the records cannot establish a "
                "safety conclusion may be supported by the explicit evidence boundary. "
                "The top-level JSON object must contain exactly overall_verdict and "
                "claims. Each claim object must contain exactly claim, verdict, "
                "evidence_global_ids, and reason. Never reproduce JSON Schema keywords "
                "such as type, properties, required, items, or additionalProperties."
            ),
            "input": json.dumps(
                {
                    "question": question["question"],
                    "candidate_answer": answer,
                    "verified_query_result": tool_result,
                },
                ensure_ascii=False,
            ),
            "text": text_format("gate3_claim_validation", schema),
            "max_output_tokens": VALIDATOR_MAX_OUTPUT_TOKENS,
        }
    )
    result = response_json(response)
    validation_errors = sorted(
        Draft202012Validator(schema).iter_errors(result),
        key=lambda error: list(error.absolute_path),
    )
    if validation_errors:
        first = validation_errors[0]
        path = ".".join(str(part) for part in first.absolute_path) or "<root>"
        raise RuntimeError(
            "Claim validator returned schema-invalid JSON at "
            f"{path}: {first.message}; returned keys={sorted(result)}"
        )
    return result, response


def canonical_fact(fact: dict[str, Any]) -> str:
    """Return a stable representation for reference-free coverage comparison."""
    return json.dumps(fact, sort_keys=True, separators=(",", ":"))


def validate_tool_coverage(
    answer: dict[str, Any], tool_result: dict[str, Any]
) -> dict[str, Any]:
    """Check that predictions cover the verified records returned for this question."""
    expected = {
        canonical_fact(record_fact(record)): record["change_id"]
        for record in tool_result["results"]
    }
    actual = {
        canonical_fact(prediction_fact(prediction))
        for prediction in answer["predictions"]
    }
    expected_facts = set(expected)
    missing = sorted(expected_facts - actual)
    unexpected = sorted(actual - expected_facts)
    return {
        "expected_record_count": len(expected_facts),
        "prediction_count": len(actual),
        "coverage_rate": (
            len(expected_facts & actual) / len(expected_facts)
            if expected_facts
            else float(not actual)
        ),
        "missing_change_ids": [expected[fact] for fact in missing],
        "unexpected_prediction_count": len(unexpected),
        "complete": not missing and not unexpected,
    }


def schema_failure_report(error: ValidationError) -> dict[str, Any]:
    """Return a compact deterministic report safe to pass into one repair call."""
    path = ".".join(str(part) for part in error.absolute_path) or "<root>"
    return {
        "schema_compliance": False,
        "status_consistent": False,
        "evidence_support_rate": 0.0,
        "schema_error": {
            "path": path,
            "validator": error.validator,
            "message": error.message,
        },
    }


def repair_answer(
    client: ResponsesClient,
    question: dict[str, Any],
    answer: dict[str, Any],
    tool_result: dict[str, Any],
    structured_validation: dict[str, Any],
    tool_coverage_validation: dict[str, Any],
    claim_validation: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Perform the Proposed workflow's single controlled repair attempt."""
    response = client.create(
        {
            "instructions": (
                answer_instructions("proposed")
                + " Repair the candidate once using the validation reports. Add any "
                "missing prediction represented by a returned Change Record; remove or "
                "correct unsupported claims, unexpected predictions, and evidence. Do "
                "not add facts beyond the verified query result."
            ),
            "input": json.dumps(
                {
                    "question_id": question["question_id"],
                    "question": question["question"],
                    "candidate_answer": answer,
                    "verified_query_result": tool_result,
                    "structured_validation": structured_validation,
                    "tool_coverage_validation": tool_coverage_validation,
                    "claim_validation": claim_validation,
                },
                ensure_ascii=False,
            ),
            "text": text_format("gate3_proposed_repair", model_answer_schema()),
        }
    )
    repaired = response_json(response)["answer"]
    if repaired["question_id"] != question["question_id"]:
        raise ValueError("Repair returned a different question_id")
    return repaired, response


def run_tool_question(
    client: ResponsesClient,
    workflow: str,
    question: dict[str, Any],
    dataset_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run Tool-Using or Proposed for one question."""
    planning, call, tool_result = call_query_tool(client, question)
    answer, generated = answer_after_tool(
        client, workflow, question, planning, call, tool_result
    )
    metadata: dict[str, Any] = {
        "response_ids": [planning.get("id"), generated.get("id")],
        "tool_request": {
            "schema_version": "0.1.0",
            "filters": tool_result["filters"],
        },
        "tool_result_count": tool_result["result_count"],
        "repair_count": 0,
    }
    if workflow == "tool_using_agent":
        candidate_for(workflow, dataset_id, answer)
        return answer, metadata

    coverage = validate_tool_coverage(answer, tool_result)
    try:
        candidate = candidate_for(workflow, dataset_id, answer)
    except ValidationError as error:
        candidate = None
        structured = schema_failure_report(error)
        claims = {
            "overall_verdict": "fail",
            "claims": [],
            "validator_skipped": "candidate_schema_invalid",
        }
    else:
        structured = validate_evidence(candidate)
        claims, validation_response = validate_claims(
            client, question, answer, tool_result
        )
        metadata["response_ids"].append(validation_response.get("id"))
    metadata["initial_structured_validation"] = structured
    metadata["initial_tool_coverage_validation"] = coverage
    metadata["initial_claim_validation"] = claims
    needs_repair = (
        not structured["status_consistent"]
        or structured["evidence_support_rate"] < 1.0
        or not coverage["complete"]
        or claims["overall_verdict"] == "fail"
    )
    if needs_repair:
        answer, repair_response = repair_answer(
            client,
            question,
            answer,
            tool_result,
            structured,
            coverage,
            claims,
        )
        metadata["response_ids"].append(repair_response.get("id"))
        metadata["repair_count"] = 1
        candidate = candidate_for(workflow, dataset_id, answer)
        structured = validate_evidence(candidate)
        coverage = validate_tool_coverage(answer, tool_result)
        claims, validation_response = validate_claims(
            client, question, answer, tool_result
        )
        metadata["response_ids"].append(validation_response.get("id"))
    metadata["final_structured_validation"] = structured
    metadata["final_tool_coverage_validation"] = coverage
    metadata["final_claim_validation"] = claims
    return answer, metadata


def run_workflow(
    client: ResponsesClient,
    workflow: str,
    *,
    question_ids: set[str] | None = None,
) -> WorkflowRun:
    """Run one complete development workflow and validate its artifact."""
    if workflow not in {"direct_llm", "tool_using_agent", "proposed"}:
        raise ValueError(f"Unsupported workflow: {workflow}")
    questions_artifact = load_json(QUESTIONS_PATH)
    questions = [
        question
        for question in questions_artifact["questions"]
        if question_ids is None or question["question_id"] in question_ids
    ]
    if not questions:
        raise ValueError("No matching development questions")
    summary = load_json(MODEL_SUMMARY_PATH) if workflow == "direct_llm" else None
    answers = []
    question_metadata = []
    for question in questions:
        if workflow == "direct_llm":
            answer, metadata = run_direct_question(
                client,
                question,
                questions_artifact["dataset_id"],
                summary,
            )
        else:
            answer, metadata = run_tool_question(
                client,
                workflow,
                question,
                questions_artifact["dataset_id"],
            )
        answers.append(answer)
        question_metadata.append(
            {"question_id": question["question_id"], **metadata}
        )
    candidate = {
        "schema_version": "0.1.0",
        "dataset_id": questions_artifact["dataset_id"],
        "question_split": "development",
        "workflow": workflow,
        "answers": answers,
    }
    validate_candidate_schema(candidate)
    return WorkflowRun(candidate, {"questions": question_metadata})


def dry_run_plan(config: RunConfig) -> dict[str, Any]:
    """Describe the locked first run without sending any API request."""
    question_count = len(load_json(QUESTIONS_PATH)["questions"])
    return {
        "status": "READY_WITHOUT_API_CALL",
        "config": asdict(config),
        "question_split": "development",
        "question_count": question_count,
        "workflows": {
            "direct_llm": {
                "base_calls": question_count,
                "max_calls": question_count,
            },
            "tool_using_agent": {
                "base_calls": question_count * 2,
                "max_calls": question_count * 2,
            },
            "proposed": {
                "base_calls": question_count * 3,
                "max_calls_with_one_repair": question_count * 5,
            },
        },
        "paid_calls_made": 0,
    }
