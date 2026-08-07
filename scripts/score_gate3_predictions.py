"""Score workflow-neutral Gate 3 predictions and evidence separately."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.evidence_validation import (  # noqa: E402
    load_json,
    prediction_fact,
    validate_candidate_schema,
    validate_evidence,
)


REFERENCE_PATH = (
    REPOSITORY_ROOT
    / "evals"
    / "reference_answers"
    / "gate3-canonical-predictions.json"
)


def canonical_fact(prediction: dict[str, Any]) -> str:
    """Return one stable semantic-fact representation."""
    return json.dumps(
        prediction_fact(prediction), sort_keys=True, separators=(",", ":")
    )


def score_candidate(
    reference: dict[str, Any],
    candidate: dict[str, Any],
    *,
    allow_subset: bool = False,
    count_missing_as_failure: bool = False,
) -> dict[str, Any]:
    """Score semantic changes independently from evidence citations."""
    validate_candidate_schema(reference)
    validate_candidate_schema(candidate)
    for field in ("schema_version", "dataset_id", "question_split"):
        if candidate[field] != reference[field]:
            raise ValueError(f"Candidate {field} does not match the reference")

    all_expected_answers = {
        answer["question_id"]: answer for answer in reference["answers"]
    }
    actual_answers = {
        answer["question_id"]: answer for answer in candidate["answers"]
    }
    actual_ids = set(actual_answers)
    expected_ids = set(all_expected_answers)
    if allow_subset and count_missing_as_failure:
        raise ValueError("Choose either subset scoring or missing-as-failure scoring")
    if allow_subset:
        if not actual_ids or not actual_ids <= expected_ids:
            raise ValueError("Candidate question IDs are not a valid reference subset")
        expected_answers = {
            question_id: answer
            for question_id, answer in all_expected_answers.items()
            if question_id in actual_ids
        }
    elif count_missing_as_failure:
        if not actual_ids <= expected_ids:
            raise ValueError("Candidate contains unknown question IDs")
        expected_answers = all_expected_answers
    else:
        if expected_ids != actual_ids:
            raise ValueError("Candidate question IDs do not match the reference")
        expected_answers = all_expected_answers

    status_matches = 0
    exact_matches = 0
    true_positive = 0
    expected_total = 0
    actual_total = 0
    per_question = []
    for question_id, expected in expected_answers.items():
        actual = actual_answers.get(question_id)
        status_match = actual is not None and expected["status"] == actual["status"]
        expected_facts = {canonical_fact(item) for item in expected["predictions"]}
        actual_facts = (
            {canonical_fact(item) for item in actual["predictions"]}
            if actual is not None
            else set()
        )
        fact_match = expected_facts == actual_facts
        status_matches += int(status_match)
        exact_matches += int(status_match and fact_match)
        true_positive += len(expected_facts & actual_facts)
        expected_total += len(expected_facts)
        actual_total += len(actual_facts)
        per_question.append(
            {
                "question_id": question_id,
                "answer_present": actual is not None,
                "status_match": status_match,
                "prediction_fact_match": fact_match,
                "exact_match": status_match and fact_match,
            }
        )

    precision = true_positive / actual_total if actual_total else float(not expected_total)
    recall = true_positive / expected_total if expected_total else float(not actual_total)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    count = len(expected_answers)
    evidence_report = validate_evidence(candidate)
    return {
        "schema_compliance": True,
        "workflow": candidate["workflow"],
        "question_count": count,
        "completion_rate": len(actual_answers) / count,
        "status_accuracy": status_matches / count,
        "semantic_exact_match_accuracy": exact_matches / count,
        "change_precision": precision,
        "change_recall": recall,
        "change_f1": f1,
        "evidence_support_rate": evidence_report["evidence_support_rate"],
        "status_consistent": evidence_report["status_consistent"],
        "free_text_scored": False,
        "per_question": per_question,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path, help="Candidate answer JSON")
    parser.add_argument(
        "--allow-subset",
        action="store_true",
        help="Score a non-empty subset of the reference question IDs",
    )
    parser.add_argument(
        "--count-missing-as-failure",
        action="store_true",
        help="Score absent reference questions as failed answers",
    )
    args = parser.parse_args()
    reference = load_json(REFERENCE_PATH)
    candidate = load_json(args.candidate)
    print(
        json.dumps(
            score_candidate(
                reference,
                candidate,
                allow_subset=args.allow_subset,
                count_missing_as_failure=args.count_missing_as_failure,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
