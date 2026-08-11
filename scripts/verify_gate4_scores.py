"""Verify Gate 4 scores by regeneration and an independent metric recomputation."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from generate_gate3_reference_answers import build_canonical_predictions
from generate_gate4_blind_audit_packet import RESULTS_ROOT, require_equal
from generate_gate4_scores import (
    SCORES_PATH,
    artifact_sha256,
    build_scores,
    foundation_paths,
    load_json,
    sha256_file,
)


EXPECTED_SCORES_SHA256 = (
    "7df5bcbbf539cd8a9879cf4c5b97122fc15e96210091fbc6182b2c9a12eb3450"
)
FACT_FIELDS = (
    "change_type",
    "entity_type",
    "global_id",
    "location",
    "field",
    "old_value",
    "new_value",
)


def fact(value: dict[str, Any]) -> str:
    projected = {field: value[field] for field in FACT_FIELDS}
    return json.dumps(projected, sort_keys=True, separators=(",", ":"))


def independent_group_metrics(
    executions: list[dict[str, Any]], reference: dict[str, Any]
) -> dict[str, float]:
    expected_by_question = {
        answer["question_id"]: answer for answer in reference["answers"]
    }
    status_matches = 0
    exact_matches = 0
    true_positive = 0
    expected_total = 0
    actual_total = 0
    candidate_count = 0
    for execution in executions:
        expected = expected_by_question[execution["question_id"]]
        candidate_path = (
            RESULTS_ROOT
            / "primary"
            / execution["execution_id"]
            / "candidate.json"
        )
        actual = None
        if candidate_path.is_file():
            candidate_count += 1
            actual = load_json(candidate_path)["answers"][0]
        status_match = actual is not None and actual["status"] == expected["status"]
        expected_facts = {fact(item) for item in expected["predictions"]}
        actual_facts = (
            {fact(item) for item in actual["predictions"]}
            if actual is not None
            else set()
        )
        status_matches += int(status_match)
        exact_matches += int(status_match and expected_facts == actual_facts)
        true_positive += len(expected_facts & actual_facts)
        expected_total += len(expected_facts)
        actual_total += len(actual_facts)

    precision = true_positive / actual_total if actual_total else float(not expected_total)
    recall = true_positive / expected_total if expected_total else float(not actual_total)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    count = len(executions)
    return {
        "completion_rate": candidate_count / count,
        "status_accuracy": status_matches / count,
        "semantic_exact_match_accuracy": exact_matches / count,
        "change_precision": precision,
        "change_recall": recall,
        "change_f1": f1,
    }


def main() -> None:
    require_equal(
        artifact_sha256(SCORES_PATH), EXPECTED_SCORES_SHA256, "scores hash"
    )
    stored = load_json(SCORES_PATH)
    regenerated = build_scores()
    require_equal(stored, regenerated, "regenerated score report")

    schedule = load_json(
        Path(__file__).resolve().parents[1]
        / "evals/schedules/held_out/gate4-run-schedule.json"
    )
    reference_answers = load_json(foundation_paths()["reference_answers"])
    canonical_reference = build_canonical_predictions(reference_answers)
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for execution in schedule["executions"]:
        groups[(execution["workflow"], execution["repetition"])].append(execution)
    stored_groups = {
        (group["workflow"], group["repetition"]): group
        for group in stored["workflow_repetition_scores"]
    }
    require_equal(set(stored_groups), set(groups), "workflow/repetition groups")

    independently_checked_metrics = (
        "completion_rate",
        "status_accuracy",
        "semantic_exact_match_accuracy",
        "change_precision",
        "change_recall",
        "change_f1",
    )
    for key, executions in groups.items():
        require_equal(len(executions), 40, f"{key} execution count")
        independent = independent_group_metrics(executions, canonical_reference)
        stored_metrics = stored_groups[key]["metrics"]
        for metric in independently_checked_metrics:
            require_equal(stored_metrics[metric], independent[metric], f"{key} {metric}")

    require_equal(len(stored["execution_scores"]), 360, "execution score rows")
    require_equal(
        len({row["execution_id"] for row in stored["execution_scores"]}),
        360,
        "unique scored execution IDs",
    )
    for row in stored["execution_scores"]:
        directory = RESULTS_ROOT / "primary" / row["execution_id"]
        require_equal(sha256_file(directory / "run.json"), row["run_sha256"], "run hash")
        candidate_path = directory / "candidate.json"
        require_equal(candidate_path.is_file(), row["candidate_available"], "candidate")
        if candidate_path.is_file():
            require_equal(
                sha256_file(candidate_path), row["candidate_sha256"], "candidate hash"
            )
            require_equal(row["experimental_failure"], None, "candidate failure")
        else:
            require_equal(row["score"], None, "failure score")
            require_equal(row["candidate_sha256"], None, "failure candidate hash")

    print(
        json.dumps(
            {
                "status": "PASS",
                "scores_sha256": artifact_sha256(SCORES_PATH),
                "exact_regeneration_match": True,
                "independently_recomputed_metrics": list(
                    independently_checked_metrics
                ),
                "workflow_repetition_group_count": len(groups),
                "scored_execution_count": len(stored["execution_scores"]),
                "unique_execution_count": 360,
                "model_calls_made": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
