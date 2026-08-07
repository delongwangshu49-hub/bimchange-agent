"""Generate the fixed non-diff model summary for the Direct LLM baseline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import ifcopenshell
from ifcopenshell.util.element import get_container, get_psets
from jsonschema import Draft202012Validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
GROUND_TRUTH_PATH = (
    REPOSITORY_ROOT / "data" / "ground_truth" / "gate2-change-records.json"
)
SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "model-pair-summary.schema.json"
OUTPUT_PATH = (
    REPOSITORY_ROOT
    / "evals"
    / "inputs"
    / "development"
    / "gate3-model-pair-summary.json"
)
SCALAR_TYPES = (str, int, float, bool, type(None))


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def entity_reference(
    entity: ifcopenshell.entity_instance | None,
) -> dict[str, Any] | None:
    """Return a stable reference for one spatial entity."""
    if entity is None:
        return None
    return {
        "entity_type": entity.is_a(),
        "global_id": entity.GlobalId,
        "name": entity.Name,
    }


def element_location(element: ifcopenshell.entity_instance) -> dict[str, Any]:
    """Return direct spatial containment without inferring a missing storey."""
    container = get_container(element)
    storey = container if container and container.is_a("IfcBuildingStorey") else None
    return {
        "spatial_container": entity_reference(container),
        "building_storey": entity_reference(storey),
    }


def scalar_properties(element: ifcopenshell.entity_instance) -> list[dict[str, Any]]:
    """Flatten scalar property-set values and exclude quantities or nested values."""
    flattened = []
    for property_set, properties in sorted(get_psets(element, psets_only=True).items()):
        for name, value in sorted(properties.items()):
            if name == "id" or not isinstance(value, SCALAR_TYPES):
                continue
            flattened.append(
                {
                    "property_set": property_set,
                    "name": name,
                    "value": value,
                }
            )
    return flattened


def summarize_version(role: str, path: Path) -> dict[str, Any]:
    """Summarize one IFC version without calculating differences."""
    model = ifcopenshell.open(path)
    elements = []
    for element in sorted(model.by_type("IfcElement"), key=lambda item: item.GlobalId):
        elements.append(
            {
                "entity_type": element.is_a(),
                "global_id": element.GlobalId,
                "name": element.Name,
                "tag": element.Tag,
                "location": element_location(element),
                "properties": scalar_properties(element),
            }
        )
    return {
        "role": role,
        "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
        "sha256": sha256(path),
        "ifc_schema": model.schema,
        "element_count": len(elements),
        "elements": elements,
    }


def build_summary() -> dict[str, Any]:
    """Build and validate the fixed development input artifact."""
    ground_truth = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    source_path = REPOSITORY_ROOT / ground_truth["source_ifc"]
    revised_path = REPOSITORY_ROOT / ground_truth["revised_ifc"]
    if sha256(source_path) != ground_truth["source_sha256"]:
        raise ValueError("Source IFC hash does not match Gate 2 ground truth")
    if sha256(revised_path) != ground_truth["revised_sha256"]:
        raise ValueError("Revised IFC hash does not match Gate 2 ground truth")

    artifact = {
        "schema_version": "0.1.0",
        "dataset_id": "gate2-controlled-v0.1.0",
        "split": "development",
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
                "engineering, safety, and compliance judgments",
            ],
        },
        "versions": [
            summarize_version("source", source_path),
            summarize_version("revised", revised_path),
        ],
    }
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(artifact)
    return artifact


def main() -> None:
    artifact = build_summary()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(artifact, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(artifact, indent=2))


if __name__ == "__main__":
    main()
