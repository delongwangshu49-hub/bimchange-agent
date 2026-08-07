"""Score structured Gate 3 answers against the fixed reference artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = (
    REPOSITORY_ROOT
    / "evals"
    / "reference_answers"
    / "gate3-reference-answers.json"
)
ANSWER_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "agent-answer.schema.json"


def load_and_validate(path: Path) -> dict[str, Any]:
    """Load an answer artifact and validate its public contract."""
    artifact = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(ANSWER_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(artifact)

    question_ids = [answer["question_id"] for answer in artifact["answers"]]
    if len(question_ids) != len(set(question_ids)):
        raise ValueError(f"Duplicate question IDs in {path}")
    return artifact


def canonical_result(result: dict[str, Any]) -> str:
    """Return a stable representation for exact evidence comparison."""
    return json.dumps(result, sort_keys=True, separators=(",", ":"))


def set_metrics(expected: set[str], actual: set[str]) -> tuple[float, float, float]:
    """Calculate precision, recall, and F1 for one evidence set."""
    true_positive = len(expected & actual)
    precision = true_positive / len(actual) if actual else float(not expected)
    recall = true_positive / len(expected) if expected else float(not actual)
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return precision, recall, f1


def score_artifacts(
    reference: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    """Score status and exact structured evidence; free text is not scored here."""
    for field in (
        "schema_version",
        "dataset_id",
        "question_set_sha256",
        "change_records_sha256",
    ):
        if candidate[field] != reference[field]:
            raise ValueError(f"Candidate {field} does not match the reference")

    expected_answers = {
        answer["question_id"]: answer for answer in reference["answers"]
    }
    actual_answers = {
        answer["question_id"]: answer for answer in candidate["answers"]
    }
    if set(actual_answers) != set(expected_answers):
        missing = sorted(set(expected_answers) - set(actual_answers))
        extra = sorted(set(actual_answers) - set(expected_answers))
        raise ValueError(f"Question ID mismatch; missing={missing}, extra={extra}")

    per_question = []
    total_true_positive = 0
    total_expected = 0
    total_actual = 0
    status_matches = 0
    exact_matches = 0
    for question_id, expected_answer in expected_answers.items():
        actual_answer = actual_answers[question_id]
        status_match = actual_answer["status"] == expected_answer["status"]
        expected_results = {
            canonical_result(result) for result in expected_answer["results"]
        }
        actual_results = {
            canonical_result(result) for result in actual_answer["results"]
        }
        precision, recall, f1 = set_metrics(expected_results, actual_results)
        evidence_match = expected_results == actual_results
        exact_match = status_match and evidence_match

        status_matches += int(status_match)
        exact_matches += int(exact_match)
        total_true_positive += len(expected_results & actual_results)
        total_expected += len(expected_results)
        total_actual += len(actual_results)
        per_question.append(
            {
                "question_id": question_id,
                "status_match": status_match,
                "evidence_precision": precision,
                "evidence_recall": recall,
                "evidence_f1": f1,
                "exact_match": exact_match,
            }
        )

    question_count = len(expected_answers)
    micro_precision = (
        total_true_positive / total_actual
        if total_actual
        else float(total_expected == 0)
    )
    micro_recall = (
        total_true_positive / total_expected
        if total_expected
        else float(total_actual == 0)
    )
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if micro_precision + micro_recall
        else 0.0
    )
    return {
        "schema_compliance": True,
        "question_count": question_count,
        "status_accuracy": status_matches / question_count,
        "exact_match_accuracy": exact_matches / question_count,
        "evidence_micro_precision": micro_precision,
        "evidence_micro_recall": micro_recall,
        "evidence_micro_f1": micro_f1,
        "free_text_scored": False,
        "per_question": per_question,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "candidate",
        nargs="?",
        type=Path,
        default=REFERENCE_PATH,
        help="Candidate answer JSON (defaults to the reference artifact).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the JSON score report.",
    )
    args = parser.parse_args()

    reference = load_and_validate(REFERENCE_PATH)
    candidate = load_and_validate(args.candidate)
    report = score_artifacts(reference, candidate)
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
