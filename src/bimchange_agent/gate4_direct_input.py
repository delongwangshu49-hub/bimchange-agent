"""Build the Gate 4 Direct LLM input from two IFC inventories without a diff."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import ifcopenshell
from ifcopenshell.util.element import get_container, get_psets
from jsonschema import Draft202012Validator

from bimchange_agent.gate4_fixture import sha256
from bimchange_agent.gate4_fixture_verification import verify_production_artifacts
from bimchange_agent.gate4_foundation import REPOSITORY_ROOT, load_foundation_config


SCALAR_TYPES = (str, int, float, bool, type(None))
SCHEMA_PATH = REPOSITORY_ROOT / "schemas/model-pair-summary.schema.json"


def _reference(entity: ifcopenshell.entity_instance | None) -> dict[str, Any] | None:
    if entity is None:
        return None
    return {
        "entity_type": entity.is_a(),
        "global_id": entity.GlobalId,
        "name": entity.Name,
    }


def _location(element: ifcopenshell.entity_instance) -> dict[str, Any]:
    container = get_container(element, should_get_direct=True)
    storey = container if container and container.is_a("IfcBuildingStorey") else None
    return {
        "spatial_container": _reference(container),
        "building_storey": _reference(storey),
    }


def _properties(element: ifcopenshell.entity_instance) -> list[dict[str, Any]]:
    flattened = []
    for property_set, properties in sorted(get_psets(element, psets_only=True).items()):
        for name, value in sorted(properties.items()):
            if name == "id" or not isinstance(value, SCALAR_TYPES):
                continue
            flattened.append(
                {"property_set": property_set, "name": name, "value": value}
            )
    return flattened


def _version(role: str, path: Path) -> dict[str, Any]:
    model = ifcopenshell.open(path)
    elements = [
        {
            "entity_type": element.is_a(),
            "global_id": element.GlobalId,
            "name": element.Name,
            "tag": element.Tag,
            "location": _location(element),
            "properties": _properties(element),
        }
        for element in sorted(model.by_type("IfcElement"), key=lambda item: item.GlobalId)
    ]
    return {
        "role": role,
        "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
        "sha256": sha256(path),
        "ifc_schema": model.schema,
        "element_count": len(elements),
        "elements": elements,
    }


def build_direct_input() -> dict[str, Any]:
    """Guard fixture access, then summarize both versions independently."""
    fixture = verify_production_artifacts()
    config = load_foundation_config()
    paths = config["gate4_paths"]
    source_path = REPOSITORY_ROOT / paths["source_ifc"]
    revised_path = REPOSITORY_ROOT / paths["revised_ifc"]
    artifact = {
        "schema_version": "0.1.0",
        "dataset_id": config["dataset_id"],
        "split": config["split"],
        "scope": {
            "included": [
                "IfcElement entity type, GlobalId, Name, and Tag",
                "direct spatial container and explicit building storey",
                "scalar property-set values",
            ],
            "excluded": [
                "precomputed differences or Change Records",
                "geometry and placement coordinates",
                "materials, classifications, quantities, and nested property values",
                "engineering, safety, compliance, responsibility, and priority judgments",
            ],
        },
        "versions": [
            _version("source", source_path),
            _version("revised", revised_path),
        ],
    }
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(artifact)
    assert fixture["model_calls_made"] == 0
    return artifact


def write_production_artifact() -> dict[str, Any]:
    """Write the registered held-out Direct LLM input."""
    artifact = build_direct_input()
    path = REPOSITORY_ROOT / load_foundation_config()["gate4_paths"]["direct_input"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "PASS",
        "source_element_count": artifact["versions"][0]["element_count"],
        "revised_element_count": artifact["versions"][1]["element_count"],
        "sha256": sha256(path),
        "precomputed_differences_included": False,
        "reference_answers_included": False,
        "model_calls_made": 0,
    }
