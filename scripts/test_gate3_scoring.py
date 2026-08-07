"""Run positive and negative checks for the Gate 3 scoring contract."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from jsonschema import ValidationError

import generate_gate3_reference_answers
import score_gate3_answers


def main() -> None:
    reference = generate_gate3_reference_answers.build_reference_answers()
    positive = score_gate3_answers.score_artifacts(reference, reference)
    assert positive["exact_match_accuracy"] == 1.0
    assert positive["evidence_micro_f1"] == 1.0

    incorrect = copy.deepcopy(reference)
    summary = next(
        answer
        for answer in incorrect["answers"]
        if answer["question_id"] == "gate3-q01-summary"
    )
    summary["results"].pop()
    negative = score_gate3_answers.score_artifacts(reference, incorrect)
    assert negative["exact_match_accuracy"] < 1.0
    assert negative["evidence_micro_recall"] < 1.0

    invalid = copy.deepcopy(reference)
    invalid["answers"][0]["status"] = "unsupported-status"
    with tempfile.TemporaryDirectory(prefix="bimchange-gate3-") as directory:
        invalid_path = Path(directory) / "invalid.json"
        invalid_path.write_text(
            json.dumps(invalid, indent=2) + "\n", encoding="utf-8"
        )
        try:
            score_gate3_answers.load_and_validate(invalid_path)
        except ValidationError:
            pass
        else:
            raise AssertionError("Schema-invalid answer was accepted")

    print(
        json.dumps(
            {
                "status": "PASS",
                "positive_exact_match_accuracy": positive[
                    "exact_match_accuracy"
                ],
                "negative_exact_match_accuracy": negative[
                    "exact_match_accuracy"
                ],
                "invalid_schema_rejected": True,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
