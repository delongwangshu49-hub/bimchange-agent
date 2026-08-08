"""Build the frozen Gate 4 held-out questions and reference artifacts offline."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from bimchange_agent.change_query import record_matches
from bimchange_agent.gate4_fixture_verification import verify_production_artifacts
from bimchange_agent.gate4_foundation import (
    REPOSITORY_ROOT,
    load_foundation_config,
)


SCHEMA_VERSION = "0.1.0"
QUESTION_SCHEMA_PATH = REPOSITORY_ROOT / "schemas/evaluation-question.schema.json"
ANSWER_SCHEMA_PATH = REPOSITORY_ROOT / "schemas/agent-answer.schema.json"


@dataclass(frozen=True)
class QuestionSpec:
    """One frozen question before its deterministic reference text is rendered."""

    question_id: str
    category: str
    question: str
    selection: dict[str, Any]
    status: str
    boundary: str | None = None


QUESTION_SPECS = (
    QuestionSpec("gate3-q09-all-changes", "summary", "Summarize every verified revision event across the three building storeys.", {}, "answered"),
    QuestionSpec("gate3-q10-added-summary", "summary", "Summarize the elements that appear only in the revised IFC model.", {"change_types": ["added"]}, "answered"),
    QuestionSpec("gate3-q11-deleted-summary", "summary", "Summarize the elements that are present only in the source IFC model.", {"change_types": ["deleted"]}, "answered"),
    QuestionSpec("gate3-q12-property-summary", "summary", "Summarize all verified scalar property-value revisions.", {"change_types": ["property_modified"]}, "answered"),
    QuestionSpec("gate3-q13-beam-ground-guid", "fact_lookup", "What verified revision event involves element 3Z1rgbb$PMDfsfeWvsKUUB?", {"global_ids": ["3Z1rgbb$PMDfsfeWvsKUUB"]}, "answered"),
    QuestionSpec("gate3-q14-wall-ground-guid", "fact_lookup", "What verified revision event involves element 0z7L81IEbQPggjg__OrrlU?", {"global_ids": ["0z7L81IEbQPggjg__OrrlU"]}, "answered"),
    QuestionSpec("gate3-q15-column-level01-guid", "fact_lookup", "What verified revision event involves element 2$orIofUHKcQaHhLlr75_n?", {"global_ids": ["2$orIofUHKcQaHhLlr75_n"]}, "answered"),
    QuestionSpec("gate3-q16-slab-level01-guid", "fact_lookup", "What verified revision event involves element 3QgprvELLQBgvTF$EPliSW?", {"global_ids": ["3QgprvELLQBgvTF$EPliSW"]}, "answered"),
    QuestionSpec("gate3-q17-beam-roof-guid", "fact_lookup", "What verified revision event involves element 3JuqHVfXrLlA8tnQP5xv53?", {"global_ids": ["3JuqHVfXrLlA8tnQP5xv53"]}, "answered"),
    QuestionSpec("gate3-q18-wall-roof-guid", "fact_lookup", "What verified revision event involves element 2rg8G55UvONxUu2GmkwF$d?", {"global_ids": ["2rg8G55UvONxUu2GmkwF$d"]}, "answered"),
    QuestionSpec("gate3-q19-beam-filter", "filtered_lookup", "List the verified revision events involving IfcBeam elements.", {"entity_types": ["IfcBeam"]}, "answered"),
    QuestionSpec("gate3-q20-column-filter", "filtered_lookup", "List the verified revision events involving IfcColumn elements.", {"entity_types": ["IfcColumn"]}, "answered"),
    QuestionSpec("gate3-q21-wall-filter", "filtered_lookup", "List the verified revision events involving IfcWall elements.", {"entity_types": ["IfcWall"]}, "answered"),
    QuestionSpec("gate3-q22-slab-filter", "filtered_lookup", "List the verified revision events involving IfcSlab elements.", {"entity_types": ["IfcSlab"]}, "answered"),
    QuestionSpec("gate3-q23-ground-filter", "filtered_lookup", "Which verified revision events are explicitly associated with Ground Floor?", {"building_storey_names": ["Ground Floor"]}, "answered"),
    QuestionSpec("gate3-q24-level01-filter", "filtered_lookup", "Which verified revision events are explicitly associated with Level 01?", {"building_storey_names": ["Level 01"]}, "answered"),
    QuestionSpec("gate3-q25-roof-filter", "filtered_lookup", "Which verified revision events are explicitly associated with Roof?", {"building_storey_names": ["Roof"]}, "answered"),
    QuestionSpec("gate3-q26-added-beam-filter", "filtered_lookup", "Which IfcBeam elements were added?", {"change_types": ["added"], "entity_types": ["IfcBeam"]}, "answered"),
    QuestionSpec("gate3-q27-deleted-column-filter", "filtered_lookup", "Which IfcColumn elements were deleted?", {"change_types": ["deleted"], "entity_types": ["IfcColumn"]}, "answered"),
    QuestionSpec("gate3-q28-property-wall-filter", "filtered_lookup", "Which IfcWall elements have a verified property modification?", {"change_types": ["property_modified"], "entity_types": ["IfcWall"]}, "answered"),
    QuestionSpec("gate3-q29-beam-roof-filter", "filtered_lookup", "Which verified revision events involve an IfcBeam on Roof?", {"entity_types": ["IfcBeam"], "building_storey_names": ["Roof"]}, "answered"),
    QuestionSpec("gate3-q30-slab-ground-filter", "filtered_lookup", "Which verified revision events involve an IfcSlab on Ground Floor?", {"entity_types": ["IfcSlab"], "building_storey_names": ["Ground Floor"]}, "answered"),
    QuestionSpec("gate3-q31-added-column-level01", "filtered_lookup", "Which IfcColumn was added on Level 01?", {"change_types": ["added"], "entity_types": ["IfcColumn"], "building_storey_names": ["Level 01"]}, "answered"),
    QuestionSpec("gate3-q32-deleted-wall-ground", "filtered_lookup", "Which IfcWall was deleted from Ground Floor?", {"change_types": ["deleted"], "entity_types": ["IfcWall"], "building_storey_names": ["Ground Floor"]}, "answered"),
    QuestionSpec("gate3-q33-column-property", "property_change", "What scalar property changed for 0Iqxc9CtTOgPV$1Tej3xGK, and what are the old and new values?", {"change_types": ["property_modified"], "global_ids": ["0Iqxc9CtTOgPV$1Tej3xGK"], "property_set": "Pset_ColumnCommon", "property_name": "IsExternal"}, "answered"),
    QuestionSpec("gate3-q34-wall-property", "property_change", "What scalar property changed for 1aO4mYJaTLLf6oT4DTcfok, and what are the old and new values?", {"change_types": ["property_modified"], "global_ids": ["1aO4mYJaTLLf6oT4DTcfok"], "property_set": "Pset_WallCommon", "property_name": "FireRating"}, "answered"),
    QuestionSpec("gate3-q35-beam-property", "property_change", "What scalar property changed for 3JuqHVfXrLlA8tnQP5xv53, and what are the old and new values?", {"change_types": ["property_modified"], "global_ids": ["3JuqHVfXrLlA8tnQP5xv53"], "property_set": "Pset_BeamCommon", "property_name": "LoadBearing"}, "answered"),
    QuestionSpec("gate3-q36-slab-property", "property_change", "What scalar property changed for 2WfINAQAHRERPwEp7Nos0$, and what are the old and new values?", {"change_types": ["property_modified"], "global_ids": ["2WfINAQAHRERPwEp7Nos0$"], "property_set": "Pset_SlabCommon", "property_name": "LoadBearing"}, "answered"),
    QuestionSpec("gate3-q37-loadbearing-properties", "property_change", "Which verified property modifications affect a LoadBearing field?", {"change_types": ["property_modified"], "property_name": "LoadBearing"}, "answered"),
    QuestionSpec("gate3-q38-wall-pset-property", "property_change", "Which verified property modification affects Pset_WallCommon?", {"change_types": ["property_modified"], "property_set": "Pset_WallCommon"}, "answered"),
    QuestionSpec("gate3-q39-no-geometry", "negative_control", "Is any geometry modification verified in this revision set?", {"change_types": ["geometry_modified"]}, "not_found"),
    QuestionSpec("gate3-q40-no-added-beam-roof", "negative_control", "Was an IfcBeam added on Roof?", {"change_types": ["added"], "entity_types": ["IfcBeam"], "building_storey_names": ["Roof"]}, "not_found"),
    QuestionSpec("gate3-q41-absent-guid", "negative_control", "What verified revision event involves element 0AAAAAAAAAAAAAAAAAAAAA?", {"global_ids": ["0AAAAAAAAAAAAAAAAAAAAA"]}, "not_found"),
    QuestionSpec("gate3-q42-no-deleted-column-ground", "negative_control", "Was an IfcColumn deleted from Ground Floor?", {"change_types": ["deleted"], "entity_types": ["IfcColumn"], "building_storey_names": ["Ground Floor"]}, "not_found"),
    QuestionSpec("gate3-q43-no-property-slab-level01", "negative_control", "Did an IfcSlab on Level 01 have a verified property modification?", {"change_types": ["property_modified"], "entity_types": ["IfcSlab"], "building_storey_names": ["Level 01"]}, "not_found"),
    QuestionSpec("gate3-q44-wall-safety-boundary", "evidence_boundary", "Does deleting wall 0z7L81IEbQPggjg__OrrlU make the building structurally unsafe?", {"global_ids": ["0z7L81IEbQPggjg__OrrlU"]}, "insufficient_evidence", "structural safety"),
    QuestionSpec("gate3-q45-fire-compliance-boundary", "evidence_boundary", "Does the FireRating revision for wall 1aO4mYJaTLLf6oT4DTcfok prove regulatory compliance?", {"global_ids": ["1aO4mYJaTLLf6oT4DTcfok"]}, "insufficient_evidence", "regulatory compliance"),
    QuestionSpec("gate3-q46-beam-responsibility-boundary", "evidence_boundary", "Who is responsible for deleting beam 3TNmmeV$vP1wtU7$eM6gTb?", {"global_ids": ["3TNmmeV$vP1wtU7$eM6gTb"]}, "insufficient_evidence", "causal or contractual responsibility"),
    QuestionSpec("gate3-q47-slab-priority-boundary", "evidence_boundary", "Should added slab 1hD8Z2VI5Q48QgyBkf6YcB receive the highest coordination priority?", {"global_ids": ["1hD8Z2VI5Q48QgyBkf6YcB"]}, "insufficient_evidence", "coordination priority"),
    QuestionSpec("gate3-q48-wall-constructability-boundary", "evidence_boundary", "Is added wall 2rg8G55UvONxUu2GmkwF$d constructible as shown?", {"global_ids": ["2rg8G55UvONxUu2GmkwF$d"]}, "insufficient_evidence", "constructability"),
)


def sha256(path: Path) -> str:
    """Return a file's SHA-256 digest."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate(instance: Any, schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(instance)


def _value(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return json.dumps(value, ensure_ascii=False)


def _record_sentence(record: dict[str, Any]) -> str:
    entity = record["entity_type"]
    global_id = record["global_id"]
    storey = record["location"]["building_storey"]["name"]
    if record["change_type"] == "added":
        return f"{entity} {global_id} was added on {storey}."
    if record["change_type"] == "deleted":
        return f"{entity} {global_id} was deleted from {storey}."
    field = record["field"]
    return (
        f"{entity} {global_id} on {storey} changed "
        f"{field['property_set']}.{field['name']} from "
        f"{_value(record['old_value'])} to {_value(record['new_value'])}."
    )


def _reference_answer(
    spec: QuestionSpec, selected: list[dict[str, Any]]
) -> dict[str, Any]:
    if spec.status == "answered":
        if not selected:
            raise ValueError(f"Answered question selects no records: {spec.question_id}")
        prefix = f"{len(selected)} verified revision event"
        prefix += " matches. " if len(selected) == 1 else "s match. "
        return {
            "status": "answered",
            "answer": prefix + " ".join(_record_sentence(record) for record in selected),
            "limitations": [],
        }
    if spec.status == "not_found":
        if selected:
            raise ValueError(f"Negative control selects records: {spec.question_id}")
        limitation = (
            "The frozen comparison excludes geometry from its represented change types."
            if spec.selection.get("change_types") == ["geometry_modified"]
            else "This absence applies only to the controlled held-out revision set."
        )
        return {
            "status": "not_found",
            "answer": "No verified revision event matches the requested filters.",
            "limitations": [limitation],
        }
    if not selected or spec.boundary is None:
        raise ValueError(f"Boundary question is not grounded: {spec.question_id}")
    verified = " ".join(_record_sentence(record) for record in selected)
    return {
        "status": "insufficient_evidence",
        "answer": (
            f"The records verify the following revision fact: {verified} "
            f"They do not establish {spec.boundary}."
        ),
        "limitations": [
            f"A {spec.boundary} conclusion requires evidence and qualified assessment outside the Change Records."
        ],
    }


def build_question_and_reference_artifacts() -> tuple[dict[str, Any], dict[str, Any]]:
    """Guard fixture access, then build questions and answers without an LLM."""
    fixture = verify_production_artifacts()
    config = load_foundation_config()
    paths = config["gate4_paths"]
    records_path = REPOSITORY_ROOT / paths["change_records"]
    records_artifact = json.loads(records_path.read_text(encoding="utf-8"))
    records = records_artifact["changes"]

    questions = []
    answers = []
    for spec in QUESTION_SPECS:
        selected = sorted(
            (record for record in records if record_matches(record, spec.selection)),
            key=lambda record: record["change_id"],
        )
        reference = _reference_answer(spec, selected)
        questions.append(
            {
                "question_id": spec.question_id,
                "category": spec.category,
                "question": spec.question,
                "selection": spec.selection,
                "reference_answer": reference,
            }
        )
        answers.append(
            {
                "question_id": spec.question_id,
                "status": reference["status"],
                "answer": reference["answer"],
                "results": selected,
                "limitations": reference["limitations"],
            }
        )

    question_artifact = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": config["dataset_id"],
        "split": config["split"],
        "source_change_records": paths["change_records"],
        "questions": questions,
    }
    _validate(question_artifact, QUESTION_SCHEMA_PATH)
    question_bytes = (json.dumps(question_artifact, indent=2) + "\n").encode()
    reference_artifact = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": config["dataset_id"],
        "question_split": config["split"],
        "question_set_sha256": hashlib.sha256(question_bytes).hexdigest(),
        "change_records_sha256": sha256(records_path),
        "answers": answers,
    }
    _validate(reference_artifact, ANSWER_SCHEMA_PATH)
    assert fixture["model_calls_made"] == 0
    return question_artifact, reference_artifact


def write_production_artifacts() -> dict[str, Any]:
    """Write the registered held-out question and reference-answer artifacts."""
    question_artifact, reference_artifact = build_question_and_reference_artifacts()
    paths = load_foundation_config()["gate4_paths"]
    question_path = REPOSITORY_ROOT / paths["questions"]
    reference_path = REPOSITORY_ROOT / paths["reference_answers"]
    question_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    question_path.write_text(json.dumps(question_artifact, indent=2) + "\n", encoding="utf-8")
    reference_path.write_text(json.dumps(reference_artifact, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "PASS",
        "question_count": len(question_artifact["questions"]),
        "category_counts": dict(Counter(q["category"] for q in question_artifact["questions"])),
        "status_counts": dict(Counter(a["status"] for a in reference_artifact["answers"])),
        "question_sha256": sha256(question_path),
        "reference_answer_sha256": sha256(reference_path),
        "model_calls_made": 0,
    }
