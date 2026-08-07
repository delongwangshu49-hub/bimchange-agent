"""Offline tests for Gate 3 model configuration and orchestration boundaries."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.gate3_runner import (  # noqa: E402
    CLAIM_VALIDATION_SCHEMA_PATH,
    QUESTIONS_PATH,
    RunConfig,
    call_query_tool,
    dry_run_plan,
    load_json,
    model_answer_schema,
    query_tool,
    responses_schema_subset,
    response_json,
    validate_tool_coverage,
)


class FakePlanningClient:
    """Return one strict function call without accessing any API."""

    def create(self, payload: dict[str, object]) -> dict[str, object]:
        assert payload["parallel_tool_calls"] is False
        assert "tool_choice" not in payload
        return {
            "id": "resp_offline",
            "output": [
                {
                    "type": "function_call",
                    "name": "query_change_records",
                    "call_id": "call_offline",
                    "arguments": json.dumps(
                        {
                            "schema_version": "0.1.0",
                            "filters": {
                                "change_types": ["added"],
                                "entity_types": None,
                                "global_ids": None,
                                "building_storey_names": None,
                                "property_set": None,
                                "property_name": None,
                            },
                        }
                    ),
                }
            ],
        }


def main() -> None:
    config = RunConfig()
    assert config.provider == "deepseek"
    assert config.model == "deepseek-v4-flash"
    assert config.reasoning_effort == "high"
    plan = dry_run_plan(config)
    assert plan["paid_calls_made"] == 0
    assert plan["question_count"] == 8
    assert plan["workflows"]["direct_llm"]["base_calls"] == 8
    assert plan["workflows"]["tool_using_agent"]["base_calls"] == 16
    assert plan["workflows"]["proposed"]["base_calls"] == 24
    assert plan["workflows"]["proposed"]["max_calls_with_one_repair"] == 40

    answer_schema = model_answer_schema()
    assert answer_schema["additionalProperties"] is False
    assert answer_schema["$defs"]["prediction"]["properties"]["old_value"]["anyOf"]
    assert "oneOf" not in json.dumps(answer_schema)

    claim_schema = responses_schema_subset(load_json(CLAIM_VALIDATION_SCHEMA_PATH))
    assert claim_schema["properties"]["overall_verdict"]["type"] == "string"
    assert (
        claim_schema["properties"]["claims"]["items"]["properties"]["verdict"]["type"]
        == "string"
    )

    tool = query_tool()
    assert tool["name"] == "query_change_records"
    assert tool["strict"] is True
    assert "source_path" not in tool["parameters"]["properties"]
    filter_schema = tool["parameters"]["properties"]["filters"]
    assert set(filter_schema["required"]) == set(filter_schema["properties"])
    assert (
        filter_schema["properties"]["change_types"]["anyOf"][0]["items"]["type"]
        == "string"
    )

    added_question = next(
        question
        for question in load_json(QUESTIONS_PATH)["questions"]
        if question["question_id"] == "gate3-q02-added"
    )
    _, _, tool_result = call_query_tool(FakePlanningClient(), added_question)
    assert tool_result["filters"] == {"change_types": ["added"]}
    assert tool_result["result_count"] == 1
    missing_coverage = validate_tool_coverage({"predictions": []}, tool_result)
    assert missing_coverage["coverage_rate"] == 0.0
    assert missing_coverage["missing_change_ids"] == [
        tool_result["results"][0]["change_id"]
    ]
    covered_prediction = {
        **{
            key: value
            for key, value in tool_result["results"][0].items()
            if key
            in {
                "change_type",
                "entity_type",
                "global_id",
                "location",
                "field",
                "old_value",
                "new_value",
            }
        },
        "evidence_refs": [],
    }
    assert validate_tool_coverage(
        {"predictions": [covered_prediction]}, tool_result
    )["complete"]

    parsed = response_json(
        {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps({"answer": {"question_id": "q"}}),
                        }
                    ],
                }
            ]
        }
    )
    assert parsed["answer"]["question_id"] == "q"

    print(
        json.dumps(
            {
                "status": "PASS",
                "model": config.model,
                "reasoning_effort": config.reasoning_effort,
                "budget_usd": config.budget_usd,
                "paid_calls_made": 0,
                "direct_calls": 8,
                "tool_using_calls": 16,
                "proposed_base_calls": 24,
                "proposed_max_calls": 40,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
