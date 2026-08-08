"""Deterministic Gate 4 held-out IFC fixture generation.

This module creates synthetic IFC4 source and revised models without making any
network or model-provider calls. Production writes are guarded by the frozen
Gate 4 foundation check before any registered held-out path is accessed.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ifcopenshell
import ifcopenshell.api
from ifcopenshell.util.element import get_container, get_pset

from bimchange_agent.gate4_foundation import (
    REPOSITORY_ROOT,
    load_foundation_config,
    verify_gate4_foundation,
)


DATASET_ID = "gate4-controlled-heldout-v0.1.0"
SCHEMA_VERSION = "0.1.0"
SPLIT = "held_out"
IFC_SCHEMA = "IFC4"
FIXED_TIMESTAMP = "2026-08-08T00:00:00"
GUID_NAMESPACE = uuid.UUID("4d671ff1-671e-4cf6-a87d-cb590b175909")
CHANGE_SCHEMA_PATH = "schemas/change-record.schema.json"
DIFF_RESULT_PATH = (
    "evals/results/held_out/gate4-controlled-heldout-v0.1.0/ifcdiff.json"
)


@dataclass(frozen=True)
class StoreySpec:
    key: str
    name: str
    code: str
    elevation: float


@dataclass(frozen=True)
class EntitySpec:
    entity_type: str
    label: str
    code: str
    property_set: str
    property_name: str
    source_value: Any


@dataclass(frozen=True)
class OperationSpec:
    change_id: str
    change_type: str
    entity_type: str
    storey_key: str
    index: int
    property_set: str | None = None
    property_name: str | None = None
    old_value: Any = None
    new_value: Any = None


STOREYS = (
    StoreySpec("ground", "Ground Floor", "GF", 0.0),
    StoreySpec("level01", "Level 01", "L1", 3.2),
    StoreySpec("roof", "Roof", "RF", 6.4),
)
STOREY_BY_KEY = {storey.key: storey for storey in STOREYS}

ENTITIES = (
    EntitySpec(
        "IfcBeam", "Beam", "BM", "Pset_BeamCommon", "LoadBearing", False
    ),
    EntitySpec(
        "IfcColumn", "Column", "CL", "Pset_ColumnCommon", "IsExternal", True
    ),
    EntitySpec(
        "IfcWall", "Wall", "WL", "Pset_WallCommon", "FireRating", "60"
    ),
    EntitySpec(
        "IfcSlab", "Slab", "SL", "Pset_SlabCommon", "LoadBearing", False
    ),
)
ENTITY_BY_TYPE = {entity.entity_type: entity for entity in ENTITIES}

# Matrix order is deliberate: entity type across each storey, then the next storey.
OPERATIONS = (
    OperationSpec("gate4-added-beam-ground", "added", "IfcBeam", "ground", 5),
    OperationSpec(
        "gate4-property-column-ground",
        "property_modified",
        "IfcColumn",
        "ground",
        1,
        "Pset_ColumnCommon",
        "IsExternal",
        True,
        False,
    ),
    OperationSpec(
        "gate4-deleted-wall-ground", "deleted", "IfcWall", "ground", 1
    ),
    OperationSpec("gate4-added-slab-ground", "added", "IfcSlab", "ground", 5),
    OperationSpec(
        "gate4-deleted-beam-level01", "deleted", "IfcBeam", "level01", 1
    ),
    OperationSpec(
        "gate4-added-column-level01", "added", "IfcColumn", "level01", 5
    ),
    OperationSpec(
        "gate4-property-wall-level01",
        "property_modified",
        "IfcWall",
        "level01",
        1,
        "Pset_WallCommon",
        "FireRating",
        "60",
        "90",
    ),
    OperationSpec(
        "gate4-deleted-slab-level01", "deleted", "IfcSlab", "level01", 1
    ),
    OperationSpec(
        "gate4-property-beam-roof",
        "property_modified",
        "IfcBeam",
        "roof",
        1,
        "Pset_BeamCommon",
        "LoadBearing",
        False,
        True,
    ),
    OperationSpec(
        "gate4-deleted-column-roof", "deleted", "IfcColumn", "roof", 1
    ),
    OperationSpec("gate4-added-wall-roof", "added", "IfcWall", "roof", 5),
    OperationSpec(
        "gate4-property-slab-roof",
        "property_modified",
        "IfcSlab",
        "roof",
        1,
        "Pset_SlabCommon",
        "LoadBearing",
        False,
        True,
    ),
)


def fixed_guid(label: str) -> str:
    """Return a stable IFC-compressed UUIDv5 for a semantic label."""
    return ifcopenshell.guid.compress(uuid.uuid5(GUID_NAMESPACE, label).hex)


def element_key(entity_type: str, storey_key: str, index: int) -> str:
    return f"element:{entity_type}:{storey_key}:{index:02d}"


def element_guid(entity_type: str, storey_key: str, index: int) -> str:
    return fixed_guid(element_key(entity_type, storey_key, index))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _set_header(model: ifcopenshell.file, filename: str) -> None:
    model.header.file_name.name = filename
    model.header.file_name.time_stamp = FIXED_TIMESTAMP
    model.header.file_name.author = ("BIMChange-Agent",)
    model.header.file_name.organization = ("BIMChange-Agent",)
    model.header.file_name.preprocessor_version = "IfcOpenShell 0.8.5"
    model.header.file_name.originating_system = (
        "BIMChange-Agent deterministic fixture generator"
    )
    model.header.file_name.authorization = "Synthetic CC BY 4.0 dataset"


def _create_root(
    model: ifcopenshell.file,
    ifc_class: str,
    name: str,
    guid_label: str,
) -> ifcopenshell.entity_instance:
    entity = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class=ifc_class, name=name
    )
    entity.GlobalId = fixed_guid(guid_label)
    return entity


def _pset_relationship(
    model: ifcopenshell.file, pset: ifcopenshell.entity_instance
) -> ifcopenshell.entity_instance:
    relationships = [
        relation
        for relation in model.get_inverse(pset)
        if relation.is_a("IfcRelDefinesByProperties")
        and relation.RelatingPropertyDefinition == pset
    ]
    if len(relationships) != 1:
        raise RuntimeError(
            f"Expected one property relationship for {pset.Name}, "
            f"found {len(relationships)}"
        )
    return relationships[0]


def _create_element(
    model: ifcopenshell.file,
    entity_spec: EntitySpec,
    storey_spec: StoreySpec,
    index: int,
) -> ifcopenshell.entity_instance:
    key = element_key(entity_spec.entity_type, storey_spec.key, index)
    element = _create_root(
        model,
        entity_spec.entity_type,
        f"{entity_spec.label} {storey_spec.code} {index:02d}",
        key,
    )
    element.Tag = f"{entity_spec.code}-{storey_spec.code}-{index:02d}"

    pset = ifcopenshell.api.run(
        "pset.add_pset", model, product=element, name=entity_spec.property_set
    )
    pset.GlobalId = fixed_guid(f"pset:{key}:{entity_spec.property_set}")
    ifcopenshell.api.run(
        "pset.edit_pset",
        model,
        pset=pset,
        properties={entity_spec.property_name: entity_spec.source_value},
    )
    relationship = _pset_relationship(model, pset)
    relationship.GlobalId = fixed_guid(
        f"rel:pset:{key}:{entity_spec.property_set}"
    )
    return element


def _normalize_serialization(model: ifcopenshell.file) -> None:
    """Normalize IFC SET ordering and reject any duplicate generated GlobalId."""
    for history in model.by_type("IfcOwnerHistory"):
        if history.LastModifiedDate is not None:
            history.LastModifiedDate = 1786118400
        if history.CreationDate is not None:
            history.CreationDate = 1786118400

    for relationship in model.by_type("IfcRelAggregates"):
        relationship.RelatedObjects = sorted(
            relationship.RelatedObjects,
            key=lambda entity: (entity.GlobalId, entity.is_a()),
        )
    for relationship in model.by_type("IfcRelContainedInSpatialStructure"):
        relationship.RelatedElements = sorted(
            relationship.RelatedElements,
            key=lambda entity: (entity.GlobalId, entity.is_a()),
        )
    for relationship in model.by_type("IfcRelDefinesByProperties"):
        relationship.RelatedObjects = sorted(
            relationship.RelatedObjects,
            key=lambda entity: (entity.GlobalId, entity.is_a()),
        )

    global_ids = [root.GlobalId for root in model.by_type("IfcRoot")]
    if any(not global_id for global_id in global_ids):
        raise RuntimeError("Every generated IfcRoot must have a GlobalId")
    if len(global_ids) != len(set(global_ids)):
        raise RuntimeError("Generated IFC contains duplicate GlobalIds")


def build_source_model() -> ifcopenshell.file:
    """Build the fixed 48-element IFC4 source model in memory."""
    model = ifcopenshell.api.run("project.create_file", version=IFC_SCHEMA)
    _set_header(model, "source.ifc")

    project = _create_root(
        model, "IfcProject", "Controlled IFC Project", "spatial:project"
    )
    site = _create_root(model, "IfcSite", "Controlled Site", "spatial:site")
    building = _create_root(
        model, "IfcBuilding", "Controlled Building", "spatial:building"
    )
    storeys = {
        spec.key: _create_root(
            model,
            "IfcBuildingStorey",
            spec.name,
            f"spatial:storey:{spec.key}",
        )
        for spec in STOREYS
    }
    for spec in STOREYS:
        storeys[spec.key].Elevation = spec.elevation

    relation = ifcopenshell.api.run(
        "aggregate.assign_object", model, products=[site], relating_object=project
    )
    if relation is None:
        raise RuntimeError("Failed to aggregate site under project")
    relation.GlobalId = fixed_guid("rel:aggregate:project:site")
    relation = ifcopenshell.api.run(
        "aggregate.assign_object", model, products=[building], relating_object=site
    )
    if relation is None:
        raise RuntimeError("Failed to aggregate building under site")
    relation.GlobalId = fixed_guid("rel:aggregate:site:building")
    relation = ifcopenshell.api.run(
        "aggregate.assign_object",
        model,
        products=[storeys[spec.key] for spec in STOREYS],
        relating_object=building,
    )
    if relation is None:
        raise RuntimeError("Failed to aggregate storeys under building")
    relation.GlobalId = fixed_guid("rel:aggregate:building:storeys")

    by_storey: dict[str, list[ifcopenshell.entity_instance]] = {
        storey.key: [] for storey in STOREYS
    }
    for storey_spec in STOREYS:
        for entity_spec in ENTITIES:
            for index in range(1, 5):
                by_storey[storey_spec.key].append(
                    _create_element(model, entity_spec, storey_spec, index)
                )

    for storey_spec in STOREYS:
        relation = ifcopenshell.api.run(
            "spatial.assign_container",
            model,
            products=by_storey[storey_spec.key],
            relating_structure=storeys[storey_spec.key],
        )
        if relation is None:
            raise RuntimeError(f"Failed to contain elements in {storey_spec.name}")
        relation.GlobalId = fixed_guid(f"rel:containment:{storey_spec.key}")

    _normalize_serialization(model)
    return model


def _require_element(
    model: ifcopenshell.file, operation: OperationSpec
) -> ifcopenshell.entity_instance:
    element = model.by_guid(
        element_guid(operation.entity_type, operation.storey_key, operation.index)
    )
    if not element.is_a(operation.entity_type):
        raise RuntimeError(
            f"Expected {operation.change_id} target to be {operation.entity_type}"
        )
    return element


def build_revised_model(source_path: Path) -> ifcopenshell.file:
    """Derive the fixed revised model from a serialized source model."""
    model = ifcopenshell.open(source_path)
    _set_header(model, "revised.ifc")

    additions_by_storey: dict[str, list[ifcopenshell.entity_instance]] = {
        storey.key: [] for storey in STOREYS
    }
    for operation in OPERATIONS:
        if operation.change_type == "property_modified":
            element = _require_element(model, operation)
            pset_data = get_pset(element, operation.property_set)
            if not pset_data or "id" not in pset_data:
                raise RuntimeError(
                    f"Missing {operation.property_set} for {operation.change_id}"
                )
            actual_old = pset_data.get(operation.property_name)
            if actual_old != operation.old_value:
                raise RuntimeError(
                    f"Unexpected old value for {operation.change_id}: {actual_old!r}"
                )
            ifcopenshell.api.run(
                "pset.edit_pset",
                model,
                pset=model.by_id(pset_data["id"]),
                properties={operation.property_name: operation.new_value},
            )
        elif operation.change_type == "deleted":
            ifcopenshell.api.run(
                "root.remove_product", model, product=_require_element(model, operation)
            )
        elif operation.change_type == "added":
            additions_by_storey[operation.storey_key].append(
                _create_element(
                    model,
                    ENTITY_BY_TYPE[operation.entity_type],
                    STOREY_BY_KEY[operation.storey_key],
                    operation.index,
                )
            )
        else:
            raise RuntimeError(f"Unsupported operation: {operation.change_type}")

    for storey_key, additions in additions_by_storey.items():
        if not additions:
            continue
        storey = model.by_guid(fixed_guid(f"spatial:storey:{storey_key}"))
        relation = ifcopenshell.api.run(
            "spatial.assign_container",
            model,
            products=additions,
            relating_structure=storey,
        )
        if relation is None:
            raise RuntimeError(f"Failed to contain additions in {storey_key}")
        relation.GlobalId = fixed_guid(f"rel:containment:{storey_key}")

    _normalize_serialization(model)
    return model


def _entity_reference(entity: ifcopenshell.entity_instance) -> dict[str, Any]:
    return {
        "entity_type": entity.is_a(),
        "global_id": entity.GlobalId,
        "name": entity.Name,
    }


def _location(element: ifcopenshell.entity_instance) -> dict[str, Any]:
    container = get_container(element, should_get_direct=True)
    if container is None or not container.is_a("IfcBuildingStorey"):
        raise RuntimeError(f"Element {element.GlobalId} lacks direct storey containment")
    reference = _entity_reference(container)
    return {"spatial_container": reference, "building_storey": reference.copy()}


def _snapshot(element: ifcopenshell.entity_instance) -> dict[str, Any]:
    return {"name": element.Name, "tag": element.Tag}


def _logical_paths() -> dict[str, str]:
    config = load_foundation_config()
    paths = dict(config["gate4_paths"])
    paths["ifcdiff"] = DIFF_RESULT_PATH
    return paths


def _operation_payload(
    operation: OperationSpec,
    source_model: ifcopenshell.file,
    revised_model: ifcopenshell.file,
) -> dict[str, Any]:
    global_id = element_guid(
        operation.entity_type, operation.storey_key, operation.index
    )
    source_entity = None
    revised_entity = None
    try:
        source_entity = source_model.by_guid(global_id)
    except RuntimeError:
        pass
    try:
        revised_entity = revised_model.by_guid(global_id)
    except RuntimeError:
        pass
    location_entity = revised_entity or source_entity
    if location_entity is None:
        raise RuntimeError(f"Operation target missing from both models: {global_id}")

    before: Any = None
    after: Any = None
    field: dict[str, str] | None = None
    if operation.change_type == "added":
        after = _snapshot(revised_entity)
    elif operation.change_type == "deleted":
        before = _snapshot(source_entity)
    else:
        field = {
            "kind": "property",
            "property_set": operation.property_set,
            "name": operation.property_name,
        }
        before = operation.old_value
        after = operation.new_value

    return {
        "change_id": operation.change_id,
        "change_type": operation.change_type,
        "entity_type": operation.entity_type,
        "global_id": global_id,
        "location": _location(location_entity),
        "field": field,
        "old_value": before,
        "new_value": after,
    }


def _evidence(operation: dict[str, Any]) -> dict[str, str]:
    if operation["change_type"] != "property_modified":
        selector = operation["change_type"]
    else:
        field = operation["field"]
        selector = (
            f"changed.{operation['global_id']}.properties_changed.values_changed."
            f"root['{field['property_set']}']['{field['name']}']"
        )
    return {
        "reference_source": "controlled_revision_generator",
        "detector": "IfcDiff 0.8.5",
        "result_file": DIFF_RESULT_PATH,
        "selector": selector,
    }


def generate_artifacts(output_root: Path) -> dict[str, Any]:
    """Generate all fixture artifacts under an arbitrary clean root."""
    logical_paths = _logical_paths()
    source_path = output_root / logical_paths["source_ifc"]
    revised_path = output_root / logical_paths["revised_ifc"]
    ledger_path = output_root / logical_paths["operation_ledger"]
    records_path = output_root / logical_paths["change_records"]
    for path in (source_path, revised_path, ledger_path, records_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    source_model = build_source_model()
    source_model.write(source_path)
    revised_model = build_revised_model(source_path)
    revised_model.write(revised_path)

    source_hash = sha256(source_path)
    revised_hash = sha256(revised_path)
    operations = [
        _operation_payload(operation, source_model, revised_model)
        for operation in OPERATIONS
    ]
    ledger = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": DATASET_ID,
        "split": SPLIT,
        "ifc_schema": IFC_SCHEMA,
        "source_ifc": logical_paths["source_ifc"],
        "source_sha256": source_hash,
        "revised_ifc": logical_paths["revised_ifc"],
        "revised_sha256": revised_hash,
        "operations": operations,
    }
    change_records = {
        "schema_version": SCHEMA_VERSION,
        "schema": CHANGE_SCHEMA_PATH,
        "source_ifc": logical_paths["source_ifc"],
        "source_sha256": source_hash,
        "revised_ifc": logical_paths["revised_ifc"],
        "revised_sha256": revised_hash,
        "changes": [
            {**operation, "evidence": _evidence(operation)}
            for operation in operations
        ],
    }
    ledger_path.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    records_path.write_text(
        json.dumps(change_records, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        "status": "PASS",
        "dataset_id": DATASET_ID,
        "source_sha256": source_hash,
        "revised_sha256": revised_hash,
        "source_element_count": len(source_model.by_type("IfcElement")),
        "revised_element_count": len(revised_model.by_type("IfcElement")),
        "change_count": len(operations),
        "model_calls_made": 0,
    }


def generate_production_artifacts() -> dict[str, Any]:
    """Guard, then generate the registered held-out fixture artifacts."""
    foundation = verify_gate4_foundation()
    report = generate_artifacts(REPOSITORY_ROOT)
    return {
        **report,
        "foundation_status": foundation["status"],
        "held_out_artifacts_generated": True,
    }
