"""Offline tests for Gate 4 experimental-failure persistence."""

from __future__ import annotations

import importlib.util
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts/run_gate4_workflows.py"


def load_wrapper():
    spec = importlib.util.spec_from_file_location("gate4_wrapper_under_test", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load Gate 4 wrapper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class FrozenConfig:
    provider: str = "deepseek"
    model: str = "deepseek-v4-flash"
    reasoning_effort: str = "high"
    max_output_tokens: int = 16000
    max_transient_retries: int = 2
    budget_usd: float = 2.25
    input_usd_per_million: float = 0.14
    cached_input_usd_per_million: float = 0.0028
    output_usd_per_million: float = 0.28
    store: bool = False


class FakeLedger:
    def __init__(self) -> None:
        self.estimated_cost_usd = 0.00125

    def projected_request_cost(self, payload: dict[str, Any]) -> float:
        return 0.0001

    def public_summary(self) -> dict[str, Any]:
        return {
            "request_attempts": 1,
            "successful_responses": 1,
            "input_tokens": 100,
            "cached_input_tokens": 0,
            "output_tokens": 25,
            "estimated_cost_usd": self.estimated_cost_usd,
            "budget_usd": 2.25,
        }


class FakeInner:
    def __init__(self, response: dict[str, Any]) -> None:
        self.ledger = FakeLedger()
        self.response = response

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.response


class FailingInner:
    def __init__(self) -> None:
        self.ledger = FakeLedger()

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("DeepSeek Responses API network request failed")


def main() -> None:
    wrapper = load_wrapper()
    raw_response = {
        "id": "response-test-001",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "{invalid"}],
            }
        ],
        "usage": {"input_tokens": 100, "output_tokens": 25},
    }
    client = wrapper.CnyHardCapClient(FakeInner(raw_response), 3.96357)
    client.begin_execution("gate4-primary-test")
    returned = client.create(
        {"text": {"format": {"name": "gate3_tool_using_agent_answer"}}}
    )
    assert returned is raw_response
    assert client.provider_call_failed is False
    assert client.response_journal == [
        {
            "sequence": 1,
            "request_kind": "gate3_tool_using_agent_answer",
            "response": raw_response,
        }
    ]

    parse_error = json.JSONDecodeError("Expecting value", "", 0)
    assert (
        wrapper.experimental_failure_category(parse_error, client)
        == "schema_or_output_format"
    )

    planning_client = wrapper.CnyHardCapClient(FakeInner(raw_response), 0.0)
    planning_client.begin_execution("gate4-primary-planning-test")
    planning_client.create({"tools": [{"type": "function"}]})
    assert (
        wrapper.experimental_failure_category(parse_error, planning_client)
        == "parameter_generation"
    )
    assert (
        wrapper.experimental_failure_category(
            RuntimeError("Expected exactly one query_change_records function call"),
            planning_client,
        )
        == "tool_selection"
    )

    infrastructure_client = wrapper.CnyHardCapClient(FailingInner(), 0.0)
    infrastructure_client.begin_execution("gate4-primary-network-test")
    try:
        infrastructure_client.create({"text": {}})
    except RuntimeError as error:
        assert wrapper.experimental_failure_category(error, infrastructure_client) is None
    else:
        raise AssertionError("Infrastructure failure was not raised")

    execution = {
        "ordinal": 79,
        "execution_id": "gate4-primary-079",
        "repetition": 1,
        "workflow": "tool_using_agent",
        "question_position": 39,
        "question_id": "gate3-q09-all-changes",
        "category": "summary",
    }
    completed = [f"gate4-primary-{number:03d}" for number in range(1, 79)]
    with tempfile.TemporaryDirectory(prefix="bimchange-gate4-failure-test-") as directory:
        results_dir = Path(directory) / "results"
        checkpoint_path = results_dir / "checkpoint.json"
        wrapper.record_experimental_failure(
            execution=execution,
            error=parse_error,
            failure_category="schema_or_output_format",
            client=client,
            completed=completed,
            schedule_sha256="9" * 64,
            config=FrozenConfig(),
            provider_attributed_spend_cny=3.96357,
            results_dir=results_dir,
            checkpoint_path=checkpoint_path,
        )
        run_path = results_dir / "primary/gate4-primary-079/run.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        assert run["status"] == "EXPERIMENTAL_FAILURE"
        assert run["candidate_persisted"] is False
        assert run["raw_provider_responses"][0]["response"] == raw_response
        assert run["cumulative_usage"]["estimated_cost_usd"] == 0.00125
        assert not (run_path.parent / "candidate.json").exists()
        assert checkpoint["completed_execution_ids"][-1] == "gate4-primary-079"
        assert checkpoint["usage"] == run["cumulative_usage"]

    print(
        json.dumps(
            {
                "status": "PASS",
                "raw_response_journaled": True,
                "schema_failure_persisted_without_retry": True,
                "parameter_failure_classified": True,
                "tool_selection_failure_classified": True,
                "infrastructure_failure_remains_fatal": True,
                "exact_usage_checkpointed": True,
                "model_calls_made": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
