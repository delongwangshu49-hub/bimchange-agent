"""Test common predictions, semantic scoring, and independent evidence checks."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from jsonschema import ValidationError

import generate_gate3_direct_input
import generate_gate3_reference_answers


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.evidence_validation import (  # noqa: E402
    CHANGE_RECORD_PATH,
    MODEL_SUMMARY_PATH,
    load_json,
    prediction_fact,
    record_fact,
    validate_candidate_schema,
    validate_evidence,
)
from score_gate3_predictions import score_candidate  # noqa: E402


def write_direct_summary() -> None:
    """Regenerate the deterministic summary needed by evidence checks."""
    artifact = generate_gate3_direct_input.build_summary()
    generate_gate3_direct_input.OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    generate_gate3_direct_input.OUTPUT_PATH.write_text(
        json.dumps(artifact, indent=2) + "\n", encoding="utf-8"
    )


def canonical_reference() -> dict[str, object]:
    """Build the workflow-neutral reference artifact."""
    detailed = generate_gate3_reference_answers.build_reference_answers()
    return generate_gate3_reference_answers.build_canonical_predictions(detailed)


def with_query_evidence(reference: dict[str, object]) -> dict[str, object]:
    """Build a semantically correct Tool-Using candidate."""
    candidate = copy.deepcopy(reference)
    candidate["workflow"] = "tool_using_agent"
    records = load_json(CHANGE_RECORD_PATH)["changes"]
    source_path = CHANGE_RECORD_PATH.relative_to(REPOSITORY_ROOT).as_posix()
    for answer in candidate["answers"]:
        for prediction in answer["predictions"]:
            record = next(
                item
                for item in records
                if record_fact(item) == prediction_fact(prediction)
            )
            prediction["evidence_refs"] = [
                {
                    "source_type": "change_query",
                    "source_path": source_path,
                    "change_id": record["change_id"],
                    "global_id": record["global_id"],
                }
            ]
    return candidate


def with_summary_evidence(reference: dict[str, object]) -> dict[str, object]:
    """Build a semantically correct Direct LLM candidate."""
    candidate = copy.deepcopy(reference)
    candidate["workflow"] = "direct_llm"
    source_path = MODEL_SUMMARY_PATH.relative_to(REPOSITORY_ROOT).as_posix()
    for answer in candidate["answers"]:
        for prediction in answer["predictions"]:
            if prediction["change_type"] == "added":
                expected = (("source", False), ("revised", True))
            elif prediction["change_type"] == "deleted":
                expected = (("source", True), ("revised", False))
            else:
                expected = (("source", True), ("revised", True))
            prediction["evidence_refs"] = [
                {
                    "source_type": "model_pair_summary",
                    "source_path": source_path,
                    "version_role": role,
                    "global_id": prediction["global_id"],
                    "expected_present": present,
                    "field": prediction["field"],
                }
                for role, present in expected
            ]
    return candidate


def main() -> None:
    write_direct_summary()
    reference = canonical_reference()
    query_candidate = with_query_evidence(reference)
    direct_candidate = with_summary_evidence(reference)

    query_validation = validate_evidence(query_candidate)
    direct_validation = validate_evidence(direct_candidate)
    assert query_validation["evidence_support_rate"] == 1.0
    assert direct_validation["evidence_support_rate"] == 1.0

    perfect_score = score_candidate(reference, query_candidate)
    assert perfect_score["change_f1"] == 1.0
    assert perfect_score["evidence_support_rate"] == 1.0

    wrong_evidence = copy.deepcopy(query_candidate)
    first_prediction = next(
        prediction
        for answer in wrong_evidence["answers"]
        for prediction in answer["predictions"]
    )
    first_prediction["evidence_refs"][0]["change_id"] = "missing-change"
    wrong_evidence_score = score_candidate(reference, wrong_evidence)
    assert wrong_evidence_score["change_f1"] == 1.0
    assert wrong_evidence_score["evidence_support_rate"] < 1.0

    missing_prediction = copy.deepcopy(query_candidate)
    summary_answer = next(
        answer
        for answer in missing_prediction["answers"]
        if answer["question_id"] == "gate3-q01-summary"
    )
    summary_answer["predictions"].pop()
    missing_score = score_candidate(reference, missing_prediction)
    assert missing_score["change_recall"] < 1.0

    invalid = copy.deepcopy(query_candidate)
    invalid["workflow"] = "unknown-workflow"
    try:
        validate_candidate_schema(invalid)
    except ValidationError:
        invalid_schema_rejected = True
    else:
        raise AssertionError("Schema-invalid candidate was accepted")

    print(
        json.dumps(
            {
                "status": "PASS",
                "query_evidence_support_rate": query_validation[
                    "evidence_support_rate"
                ],
                "summary_evidence_support_rate": direct_validation[
                    "evidence_support_rate"
                ],
                "wrong_evidence_change_f1": wrong_evidence_score["change_f1"],
                "wrong_evidence_support_rate": wrong_evidence_score[
                    "evidence_support_rate"
                ],
                "missing_prediction_recall": missing_score["change_recall"],
                "invalid_schema_rejected": invalid_schema_rejected,
                "free_text_semantics_validated": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
