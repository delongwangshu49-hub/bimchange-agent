"""Independent offline verification for Gate 4 question-side artifacts."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from typing import Any

import ifcopenshell
from ifcopenshell.util.element import get_container, get_psets
from jsonschema import Draft202012Validator

from bimchange_agent.change_query import record_matches
from bimchange_agent.gate4_fixture import sha256
from bimchange_agent.gate4_fixture_verification import verify_production_artifacts
from bimchange_agent.gate4_foundation import REPOSITORY_ROOT, load_foundation_config


EXPECTED_CATEGORIES = {
    "summary": 4,
    "fact_lookup": 6,
    "filtered_lookup": 14,
    "property_change": 6,
    "negative_control": 5,
    "evidence_boundary": 5,
}
EXPECTED_STATUSES = {"answered": 30, "not_found": 5, "insufficient_evidence": 5}
GUID_PATTERN = re.compile(r"[0-3][0-9A-Za-z_$]{21}")
FORBIDDEN_DIRECT_KEYS = {
    "change_id",
    "change_type",
    "changes",
    "evidence",
    "limitations",
    "new_value",
    "old_value",
    "predictions",
    "reference_answer",
    "results",
    "selection",
}


def _validate(instance: Any, relative_schema_path: str) -> None:
    schema = json.loads(
        (REPOSITORY_ROOT / relative_schema_path).read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(instance)


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(normalized.split())


def _selected(
    records: list[dict[str, Any]], selection: dict[str, Any]
) -> list[dict[str, Any]]:
    return sorted(
        (record for record in records if record_matches(record, selection)),
        key=lambda record: record["change_id"],
    )


def _recursive_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(
            *(_recursive_keys(item) for item in value.values()), set()
        )
    if isinstance(value, list):
        return set().union(*(_recursive_keys(item) for item in value), set())
    return set()


def _recursive_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _recursive_strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _recursive_strings(item)]
    return []


def _development_guids() -> set[str]:
    sources = (
        REPOSITORY_ROOT / "evals/questions/gate3-questions.json",
        REPOSITORY_ROOT / "data/ground_truth/gate2-change-records.json",
    )
    return set().union(
        *(set(GUID_PATTERN.findall(path.read_text(encoding="utf-8"))) for path in sources)
    )


def verify_question_and_reference_contract(
    questions: dict[str, Any],
    references: dict[str, Any],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Verify schema, selection semantics, coverage, independence, and grounding."""
    _validate(questions, "schemas/evaluation-question.schema.json")
    _validate(references, "schemas/agent-answer.schema.json")
    assert questions["dataset_id"] == references["dataset_id"]
    assert questions["split"] == references["question_split"] == "held_out"
    assert len(questions["questions"]) == len(references["answers"]) == 40

    question_ids = [question["question_id"] for question in questions["questions"]]
    assert len(question_ids) == len(set(question_ids))
    assert [int(question_id[7:9]) for question_id in question_ids] == list(range(9, 49))
    assert Counter(q["category"] for q in questions["questions"]) == EXPECTED_CATEGORIES
    assert Counter(a["status"] for a in references["answers"]) == EXPECTED_STATUSES

    rendered_questions = (json.dumps(questions, indent=2) + "\n").encode()
    assert references["question_set_sha256"] == hashlib.sha256(
        rendered_questions
    ).hexdigest()
    reference_by_id = {answer["question_id"]: answer for answer in references["answers"]}
    assert set(reference_by_id) == set(question_ids)

    development = json.loads(
        (REPOSITORY_ROOT / "evals/questions/gate3-questions.json").read_text(
            encoding="utf-8"
        )
    )
    development_texts = {
        _normalize(question["question"]) for question in development["questions"]
    }
    held_out_texts = [_normalize(question["question"]) for question in questions["questions"]]
    assert len(held_out_texts) == len(set(held_out_texts))
    assert not set(held_out_texts) & development_texts

    serialized = json.dumps(
        {"questions": questions, "references": references}, ensure_ascii=False
    )
    assert not (_development_guids() & set(GUID_PATTERN.findall(serialized)))

    record_ids = {record["change_id"] for record in records}
    non_summary_coverage: Counter[str] = Counter()
    summary_coverage: Counter[str] = Counter()
    property_category_coverage: Counter[str] = Counter()
    filtered_keysets = set()
    negative_selections = []
    boundary_questions = []
    for question in questions["questions"]:
        answer = reference_by_id[question["question_id"]]
        expected = _selected(records, question["selection"])
        embedded = question["reference_answer"]
        assert answer["status"] == embedded["status"]
        assert answer["answer"] == embedded["answer"]
        assert answer["limitations"] == embedded["limitations"]
        assert answer["results"] == expected
        if answer["status"] == "answered":
            assert expected
        elif answer["status"] == "not_found":
            assert not expected
            negative_selections.append(question["selection"])
        else:
            assert expected
            assert "do not establish" in answer["answer"]
            assert answer["limitations"]
            boundary_questions.append(question["question"].casefold())

        selected_ids = {record["change_id"] for record in expected}
        if question["category"] == "summary":
            summary_coverage.update(selected_ids)
        elif question["category"] != "negative_control":
            non_summary_coverage.update(selected_ids)
        if question["category"] == "property_change":
            property_category_coverage.update(selected_ids)
        if question["category"] == "filtered_lookup":
            filtered_keysets.add(frozenset(question["selection"]))
            forbidden = re.compile(r"\b(sort|highest|lowest|why|cause|average|total)\b")
            assert forbidden.search(question["question"].casefold()) is None

        reference_text = _normalize(answer["answer"])
        assert reference_text not in _normalize(question["question"])

    assert set(non_summary_coverage) == record_ids
    assert min(non_summary_coverage.values()) >= 2
    assert set(summary_coverage) == record_ids
    assert min(summary_coverage.values()) >= 1
    property_record_ids = {
        record["change_id"]
        for record in records
        if record["change_type"] == "property_modified"
    }
    assert property_record_ids <= set(property_category_coverage)

    assert any(len(keys) == 1 for keys in filtered_keysets)
    assert frozenset({"change_types", "entity_types"}) in filtered_keysets
    assert frozenset({"entity_types", "building_storey_names"}) in filtered_keysets
    assert frozenset(
        {"change_types", "entity_types", "building_storey_names"}
    ) in filtered_keysets

    assert any(s.get("change_types") == ["geometry_modified"] for s in negative_selections)
    assert any(
        "entity_types" in selection and "building_storey_names" in selection
        for selection in negative_selections
    )
    record_guids = {record["global_id"] for record in records}
    assert any(
        set(selection.get("global_ids", [])) - record_guids
        for selection in negative_selections
    )
    boundary_text = " ".join(boundary_questions)
    for concept in ("unsafe", "compliance", "responsible", "priority", "constructible"):
        assert concept in boundary_text

    return {
        "category_counts": dict(Counter(q["category"] for q in questions["questions"])),
        "status_counts": dict(Counter(a["status"] for a in references["answers"])),
        "minimum_non_summary_coverage": min(non_summary_coverage.values()),
        "minimum_summary_coverage": min(summary_coverage.values()),
        "normalized_development_matches": 0,
        "development_global_ids_found": 0,
    }


def _expected_element(element: ifcopenshell.entity_instance) -> dict[str, Any]:
    container = get_container(element, should_get_direct=True)
    reference = {
        "entity_type": container.is_a(),
        "global_id": container.GlobalId,
        "name": container.Name,
    }
    properties = []
    for property_set, values in sorted(get_psets(element, psets_only=True).items()):
        for name, value in sorted(values.items()):
            if name == "id" or not isinstance(value, (str, int, float, bool, type(None))):
                continue
            properties.append({"property_set": property_set, "name": name, "value": value})
    return {
        "entity_type": element.is_a(),
        "global_id": element.GlobalId,
        "name": element.Name,
        "tag": element.Tag,
        "location": {"spatial_container": reference, "building_storey": reference.copy()},
        "properties": properties,
    }


def verify_direct_input_contract(
    direct_input: dict[str, Any],
    references: dict[str, Any],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Verify the Direct input is exactly two independently checked inventories."""
    _validate(direct_input, "schemas/model-pair-summary.schema.json")
    config = load_foundation_config()
    paths = config["gate4_paths"]
    assert direct_input["dataset_id"] == config["dataset_id"]
    assert direct_input["split"] == "held_out"
    assert [version["role"] for version in direct_input["versions"]] == [
        "source",
        "revised",
    ]
    assert not (_recursive_keys(direct_input) & FORBIDDEN_DIRECT_KEYS)

    for role, version in zip(("source", "revised"), direct_input["versions"]):
        path = REPOSITORY_ROOT / paths[f"{role}_ifc"]
        assert version["path"] == paths[f"{role}_ifc"]
        assert version["sha256"] == sha256(path)
        model = ifcopenshell.open(path)
        expected = [
            _expected_element(element)
            for element in sorted(model.by_type("IfcElement"), key=lambda item: item.GlobalId)
        ]
        assert version["ifc_schema"] == model.schema == "IFC4"
        assert version["element_count"] == len(expected) == 48
        assert version["elements"] == expected

    serialized = _normalize(json.dumps(direct_input, ensure_ascii=False))
    direct_strings = [_normalize(text) for text in _recursive_strings(direct_input)]
    for record in records:
        assert _normalize(record["change_id"]) not in serialized
    for answer in references["answers"]:
        answer_text = _normalize(answer["answer"])
        assert not any(answer_text in text for text in direct_strings)
        for limitation in answer["limitations"]:
            limitation_text = _normalize(limitation)
            assert not any(limitation_text in text for text in direct_strings)
    assert not (_development_guids() & set(GUID_PATTERN.findall(json.dumps(direct_input))))
    return {
        "version_count": 2,
        "source_element_count": direct_input["versions"][0]["element_count"],
        "revised_element_count": direct_input["versions"][1]["element_count"],
        "forbidden_direct_keys_found": 0,
        "reference_answer_leaks_found": 0,
        "precomputed_change_ids_found": 0,
    }


def verify_production_question_artifacts() -> dict[str, Any]:
    """Guard, then verify all three registered pre-call content artifacts."""
    fixture = verify_production_artifacts()
    config = load_foundation_config()
    paths = config["gate4_paths"]
    records_path = REPOSITORY_ROOT / paths["change_records"]
    question_path = REPOSITORY_ROOT / paths["questions"]
    reference_path = REPOSITORY_ROOT / paths["reference_answers"]
    direct_path = REPOSITORY_ROOT / paths["direct_input"]
    records = json.loads(records_path.read_text(encoding="utf-8"))["changes"]
    questions = json.loads(question_path.read_text(encoding="utf-8"))
    references = json.loads(reference_path.read_text(encoding="utf-8"))
    direct_input = json.loads(direct_path.read_text(encoding="utf-8"))
    assert references["change_records_sha256"] == sha256(records_path)

    question_report = verify_question_and_reference_contract(
        questions, references, records
    )
    direct_report = verify_direct_input_contract(direct_input, references, records)

    from bimchange_agent.gate4_direct_input import build_direct_input
    from bimchange_agent.gate4_question_artifacts import (
        build_question_and_reference_artifacts,
    )

    regenerated_questions, regenerated_references = (
        build_question_and_reference_artifacts()
    )
    assert regenerated_questions == questions
    assert regenerated_references == references
    assert build_direct_input() == direct_input

    return {
        "status": "PASS",
        "foundation_status": fixture["foundation_status"],
        "fixture_status": fixture["status"],
        "dataset_id": config["dataset_id"],
        "question_count": len(questions["questions"]),
        **question_report,
        **direct_report,
        "question_sha256": sha256(question_path),
        "reference_answer_sha256": sha256(reference_path),
        "direct_input_sha256": sha256(direct_path),
        "clean_regeneration_byte_identical": True,
        "held_out_artifacts_read": True,
        "model_calls_made": 0,
    }
