"""Generate the controlled multi-change IFC revision used for Gate 2."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.api
from ifcopenshell.util.element import copy_deep, get_container, get_pset


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = REPOSITORY_ROOT / "data" / "raw" / "Building-Structural.ifc"
REVISED_PATH = (
    REPOSITORY_ROOT / "data" / "generated" / "Building-Structural-gate2-v2.ifc"
)
GROUND_TRUTH_PATH = (
    REPOSITORY_ROOT / "data" / "ground_truth" / "gate2-change-records.json"
)
DIFF_PATH = REPOSITORY_ROOT / "evals" / "results" / "gate2-ifcdiff.json"
SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "change-record.schema.json"

PROPERTY_TARGET_GLOBAL_ID = "2ddLgAnQf4mBfh5IpUp54U"
PROPERTY_SET = "Pset_BeamCommon"
PROPERTY = "IsExternal"
EXPECTED_OLD_VALUE = False
NEW_VALUE = True

ADDITION_SOURCE_GLOBAL_ID = "2fjJuPht9EIQaZQYZfC1Op"
ADDED_GLOBAL_ID = ifcopenshell.guid.compress(
    uuid.UUID("7c2f61c7-ec98-4a1c-94a8-d54182d1e418").hex
)
ADDED_CONTAINMENT_GLOBAL_ID = ifcopenshell.guid.compress(
    uuid.UUID("9b7284c2-4236-41ba-828c-5146a478cf6e").hex
)
ADDED_NAME = "Gate 2 added beam"
ADDED_TAG = "GATE2-ADDED-BEAM"

DELETED_GLOBAL_ID = "0DyViLJJ175RvWQi1rE7a6"
FIXED_HISTORY_TIMESTAMP = 1731578952


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def entity_snapshot(entity: ifcopenshell.entity_instance) -> dict[str, Any]:
    """Return the deliberately small before/after value used by the records."""
    return {
        "name": entity.Name,
        "tag": entity.Tag,
    }


def entity_reference(
    entity: ifcopenshell.entity_instance | None,
) -> dict[str, Any] | None:
    """Return a stable reference for a spatial IFC entity, if one exists."""
    if entity is None:
        return None
    return {
        "entity_type": entity.is_a(),
        "global_id": entity.GlobalId,
        "name": entity.Name,
    }


def element_location(element: ifcopenshell.entity_instance) -> dict[str, Any]:
    """Record the direct spatial container and a storey when it is available."""
    container = get_container(element)
    storey = container if container and container.is_a("IfcBuildingStorey") else None
    return {
        "spatial_container": entity_reference(container),
        "building_storey": entity_reference(storey),
    }


def require_type(
    model: ifcopenshell.file,
    global_id: str,
    expected_type: str,
) -> ifcopenshell.entity_instance:
    """Return a known entity and fail clearly if the sample has drifted."""
    entity = model.by_guid(global_id)
    if not entity.is_a(expected_type):
        raise RuntimeError(
            f"Expected {global_id} to be {expected_type}, got {entity.is_a()}"
        )
    return entity


def normalize_generated_serialization(model: ifcopenshell.file) -> None:
    """Remove timestamp and IFC SET ordering noise from the generated fixture."""
    for history in model.by_type("IfcOwnerHistory"):
        if history.LastModifiedDate is not None:
            history.LastModifiedDate = FIXED_HISTORY_TIMESTAMP

    for relation in model.by_type("IfcRelContainedInSpatialStructure"):
        relation.RelatedElements = sorted(
            relation.RelatedElements,
            key=lambda entity: (entity.GlobalId, entity.is_a()),
        )

    for relation in model.by_type("IfcRelAssociatesMaterial"):
        relation.RelatedObjects = sorted(
            relation.RelatedObjects,
            key=lambda entity: (
                getattr(entity, "GlobalId", "") or "",
                entity.is_a(),
            ),
        )


def main() -> None:
    model = ifcopenshell.open(SOURCE_PATH)

    property_target = require_type(
        model, PROPERTY_TARGET_GLOBAL_ID, "IfcBeam"
    )
    pset_data = get_pset(property_target, PROPERTY_SET)
    if not pset_data or "id" not in pset_data:
        raise RuntimeError(f"Property set not found: {PROPERTY_SET}")
    old_value = pset_data.get(PROPERTY)
    if old_value != EXPECTED_OLD_VALUE:
        raise RuntimeError(
            f"Expected {PROPERTY_SET}.{PROPERTY}={EXPECTED_OLD_VALUE!r}, "
            f"got {old_value!r}"
        )
    ifcopenshell.api.run(
        "pset.edit_pset",
        model,
        pset=model.by_id(pset_data["id"]),
        properties={PROPERTY: NEW_VALUE},
    )

    addition_source = require_type(model, ADDITION_SOURCE_GLOBAL_ID, "IfcBeam")
    source_container = get_container(addition_source)
    if source_container is None:
        raise RuntimeError(
            f"Addition source has no spatial container: {ADDITION_SOURCE_GLOBAL_ID}"
        )
    added = copy_deep(model, addition_source)
    added.GlobalId = ADDED_GLOBAL_ID
    added.Name = ADDED_NAME
    added.Tag = ADDED_TAG
    containment_relation = ifcopenshell.api.run(
        "spatial.assign_container",
        model,
        products=[added],
        relating_structure=source_container,
    )
    if containment_relation is None:
        raise RuntimeError("IfcOpenShell did not create the expected containment relation")
    containment_relation.GlobalId = ADDED_CONTAINMENT_GLOBAL_ID

    deleted = require_type(model, DELETED_GLOBAL_ID, "IfcWall")
    deleted_entity_type = deleted.is_a()
    deleted_global_id = deleted.GlobalId
    deleted_snapshot = entity_snapshot(deleted)
    deleted_location = element_location(deleted)
    ifcopenshell.api.run("root.remove_product", model, product=deleted)

    normalize_generated_serialization(model)

    REVISED_PATH.parent.mkdir(parents=True, exist_ok=True)
    GROUND_TRUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.write(REVISED_PATH)

    ground_truth = {
        "schema_version": "0.1.0",
        "schema": SCHEMA_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
        "source_ifc": SOURCE_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
        "source_sha256": sha256(SOURCE_PATH),
        "revised_ifc": REVISED_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
        "revised_sha256": sha256(REVISED_PATH),
        "changes": [
            {
                "change_id": "gate2-property-001",
                "change_type": "property_modified",
                "entity_type": property_target.is_a(),
                "global_id": property_target.GlobalId,
                "location": element_location(property_target),
                "field": {
                    "kind": "property",
                    "property_set": PROPERTY_SET,
                    "name": PROPERTY,
                },
                "old_value": old_value,
                "new_value": NEW_VALUE,
                "evidence": {
                    "reference_source": "controlled_revision_generator",
                    "detector": "IfcDiff 0.8.5",
                    "result_file": DIFF_PATH.relative_to(
                        REPOSITORY_ROOT
                    ).as_posix(),
                    "selector": (
                        f"changed.{property_target.GlobalId}.properties_changed"
                        f".values_changed.root['{PROPERTY_SET}']['{PROPERTY}']"
                    ),
                },
            },
            {
                "change_id": "gate2-added-001",
                "change_type": "added",
                "entity_type": added.is_a(),
                "global_id": added.GlobalId,
                "location": element_location(added),
                "field": None,
                "old_value": None,
                "new_value": entity_snapshot(added),
                "evidence": {
                    "reference_source": "controlled_revision_generator",
                    "detector": "IfcDiff 0.8.5",
                    "result_file": DIFF_PATH.relative_to(
                        REPOSITORY_ROOT
                    ).as_posix(),
                    "selector": "added",
                },
            },
            {
                "change_id": "gate2-deleted-001",
                "change_type": "deleted",
                "entity_type": deleted_entity_type,
                "global_id": deleted_global_id,
                "location": deleted_location,
                "field": None,
                "old_value": deleted_snapshot,
                "new_value": None,
                "evidence": {
                    "reference_source": "controlled_revision_generator",
                    "detector": "IfcDiff 0.8.5",
                    "result_file": DIFF_PATH.relative_to(
                        REPOSITORY_ROOT
                    ).as_posix(),
                    "selector": "deleted",
                },
            },
        ],
    }
    GROUND_TRUTH_PATH.write_text(
        json.dumps(ground_truth, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(ground_truth, indent=2))


if __name__ == "__main__":
    main()
