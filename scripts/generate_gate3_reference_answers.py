"""Generate Gate 3 reference answers from questions and Change Records."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.change_query import record_matches  # noqa: E402


QUESTION_PATH = REPOSITORY_ROOT / "evals" / "questions" / "gate3-questions.json"
QUESTION_SCHEMA_PATH = (
    REPOSITORY_ROOT / "schemas" / "evaluation-question.schema.json"
)
ANSWER_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "agent-answer.schema.json"
OUTPUT_PATH = (
    REPOSITORY_ROOT
    / "evals"
    / "reference_answers"
    / "gate3-reference-answers.json"
)


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate(instance: Any, schema_path: Path) -> None:
    """Validate an instance with a Draft 2020-12 JSON Schema."""
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(instance)


def build_reference_answers() -> dict[str, Any]:
    """Build deterministic reference answers without calling a language model."""
    question_set = json.loads(QUESTION_PATH.read_text(encoding="utf-8"))
    validate(question_set, QUESTION_SCHEMA_PATH)

    question_ids = [question["question_id"] for question in question_set["questions"]]
    if len(question_ids) != len(set(question_ids)):
        raise ValueError("Question IDs must be unique")

    change_record_path = REPOSITORY_ROOT / question_set["source_change_records"]
    change_records = json.loads(change_record_path.read_text(encoding="utf-8"))
    answers = []
    for question in question_set["questions"]:
        selected = sorted(
            (
                record
                for record in change_records["changes"]
                if record_matches(record, question["selection"])
            ),
            key=lambda record: record["change_id"],
        )
        reference = question["reference_answer"]
        if reference["status"] == "answered" and not selected:
            raise ValueError(
                f"Answered question selected no records: {question['question_id']}"
            )
        if reference["status"] == "not_found" and selected:
            raise ValueError(
                f"Not-found question selected records: {question['question_id']}"
            )
        answers.append(
            {
                "question_id": question["question_id"],
                "status": reference["status"],
                "answer": reference["answer"],
                "results": selected,
                "limitations": reference["limitations"],
            }
        )

    artifact = {
        "schema_version": "0.1.0",
        "dataset_id": question_set["dataset_id"],
        "question_split": question_set["split"],
        "question_set_sha256": sha256(QUESTION_PATH),
        "change_records_sha256": sha256(change_record_path),
        "answers": answers,
    }
    validate(artifact, ANSWER_SCHEMA_PATH)
    return artifact


def main() -> None:
    artifact = build_reference_answers()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(artifact, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(artifact, indent=2))


if __name__ == "__main__":
    main()
