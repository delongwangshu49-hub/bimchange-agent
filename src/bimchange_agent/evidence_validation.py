"""Validate structured prediction evidence independently of reference answers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_SCHEMA_PATH = (
    REPOSITORY_ROOT / "schemas" / "candidate-answer.schema.json"
)
CHANGE_RECORD_PATH = (
    REPOSITORY_ROOT / "data" / "ground_truth" / "gate2-change-records.json"
)
MODEL_SUMMARY_PATH = (
    REPOSITORY_ROOT
    / "evals"
    / "inputs"
    / "development"
    / "gate3-model-pair-summary.json"
)


def load_json(path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON object."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"Expected a JSON object: {path}")
    return data


def validate_candidate_schema(candidate: dict[str, Any]) -> None:
    """Validate the common cross-workflow candidate format."""
    schema = load_json(CANDIDATE_SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(candidate)
    question_ids = [answer["question_id"] for answer in candidate["answers"]]
    if len(question_ids) != len(set(question_ids)):
        raise ValueError("Candidate question IDs must be unique")


def prediction_fact(prediction: dict[str, Any]) -> dict[str, Any]:
    """Return only semantic prediction fields, excluding evidence citations."""
    return {
        "change_type": prediction["change_type"],
        "entity_type": prediction["entity_type"],
        "global_id": prediction["global_id"],
        "location": prediction["location"],
        "field": prediction["field"],
        "old_value": prediction["old_value"],
        "new_value": prediction["new_value"],
    }


def record_fact(record: dict[str, Any]) -> dict[str, Any]:
    """Project one Change Record to the same semantic fields as a prediction."""
    return {
        "change_type": record["change_type"],
        "entity_type": record["entity_type"],
        "global_id": record["global_id"],
        "location": record["location"],
        "field": record["field"],
        "old_value": record["old_value"],
        "new_value": record["new_value"],
    }


def scalar_property(
    element: dict[str, Any], field: dict[str, Any]
) -> Any:
    """Return one scalar property value from a model-summary element."""
    matches = [
        item["value"]
        for item in element["properties"]
        if item["property_set"] == field["property_set"]
        and item["name"] == field["name"]
    ]
    if len(matches) != 1:
        raise KeyError(
            f"Expected one summarized value for {field['property_set']}.{field['name']}"
        )
    return matches[0]


def summary_evidence_supports(
    prediction: dict[str, Any],
    refs: list[dict[str, Any]],
    summary_index: dict[tuple[str, str], dict[str, Any]],
) -> bool:
    """Check whether version-specific summary citations support one prediction."""
    expected_path = MODEL_SUMMARY_PATH.relative_to(REPOSITORY_ROOT).as_posix()
    relevant = [
        ref
        for ref in refs
        if ref["source_type"] == "model_pair_summary"
        and ref["source_path"] == expected_path
        and ref["global_id"] == prediction["global_id"]
        and ref["field"] == prediction["field"]
    ]
    cited = {(ref["version_role"], ref["expected_present"]): ref for ref in relevant}

    def presence_matches(role: str, expected_present: bool) -> bool:
        ref = cited.get((role, expected_present))
        if ref is None:
            return False
        return ((role, prediction["global_id"]) in summary_index) == expected_present

    change_type = prediction["change_type"]
    if change_type == "added":
        if not presence_matches("source", False) or not presence_matches(
            "revised", True
        ):
            return False
        revised = summary_index[("revised", prediction["global_id"])]
        return (
            revised["entity_type"] == prediction["entity_type"]
            and revised["location"] == prediction["location"]
            and {
                "name": revised["name"],
                "tag": revised["tag"],
            }
            == prediction["new_value"]
            and prediction["old_value"] is None
        )
    if change_type == "deleted":
        if not presence_matches("source", True) or not presence_matches(
            "revised", False
        ):
            return False
        source = summary_index[("source", prediction["global_id"])]
        return (
            source["entity_type"] == prediction["entity_type"]
            and source["location"] == prediction["location"]
            and {"name": source["name"], "tag": source["tag"]}
            == prediction["old_value"]
            and prediction["new_value"] is None
        )
    if change_type == "property_modified" and prediction["field"] is not None:
        if not presence_matches("source", True) or not presence_matches(
            "revised", True
        ):
            return False
        source = summary_index[("source", prediction["global_id"])]
        revised = summary_index[("revised", prediction["global_id"])]
        if source["entity_type"] != prediction["entity_type"]:
            return False
        if revised["location"] != prediction["location"]:
            return False
        return (
            scalar_property(source, prediction["field"])
            == prediction["old_value"]
            and scalar_property(revised, prediction["field"])
            == prediction["new_value"]
        )
    return False


def query_evidence_supports(
    prediction: dict[str, Any],
    refs: list[dict[str, Any]],
    records_by_id: dict[str, dict[str, Any]],
) -> bool:
    """Check whether a cited query result exactly supports one prediction."""
    expected_path = CHANGE_RECORD_PATH.relative_to(REPOSITORY_ROOT).as_posix()
    for ref in refs:
        if ref["source_type"] != "change_query":
            continue
        if ref["source_path"] != expected_path:
            continue
        record = records_by_id.get(ref["change_id"])
        if record is None or ref["global_id"] != prediction["global_id"]:
            continue
        if record_fact(record) == prediction_fact(prediction):
            return True
    return False


def validate_evidence(candidate: dict[str, Any]) -> dict[str, Any]:
    """Validate candidate structure, status rules, and prediction evidence."""
    validate_candidate_schema(candidate)
    records = load_json(CHANGE_RECORD_PATH)["changes"]
    records_by_id = {record["change_id"]: record for record in records}
    summary = load_json(MODEL_SUMMARY_PATH)
    summary_index = {
        (version["role"], element["global_id"]): element
        for version in summary["versions"]
        for element in version["elements"]
    }

    unsupported = []
    status_violations = []
    prediction_count = 0
    supported_count = 0
    for answer in candidate["answers"]:
        predictions = answer["predictions"]
        if answer["status"] == "answered" and not predictions:
            status_violations.append(
                {"question_id": answer["question_id"], "reason": "answered_without_prediction"}
            )
        if answer["status"] == "not_found" and predictions:
            status_violations.append(
                {"question_id": answer["question_id"], "reason": "not_found_with_prediction"}
            )
        if answer["status"] == "insufficient_evidence" and not answer[
            "limitations"
        ]:
            status_violations.append(
                {
                    "question_id": answer["question_id"],
                    "reason": "insufficient_evidence_without_limitation",
                }
            )

        for index, prediction in enumerate(predictions):
            prediction_count += 1
            refs = prediction["evidence_refs"]
            supported = query_evidence_supports(
                prediction, refs, records_by_id
            ) or summary_evidence_supports(prediction, refs, summary_index)
            supported_count += int(supported)
            if not supported:
                unsupported.append(
                    {
                        "question_id": answer["question_id"],
                        "prediction_index": index,
                        "global_id": prediction["global_id"],
                    }
                )

    return {
        "schema_compliance": True,
        "status_consistent": not status_violations,
        "status_violations": status_violations,
        "prediction_count": prediction_count,
        "evidence_supported_count": supported_count,
        "evidence_support_rate": (
            supported_count / prediction_count if prediction_count else 1.0
        ),
        "unsupported_predictions": unsupported,
        "free_text_semantics_validated": False,
    }
