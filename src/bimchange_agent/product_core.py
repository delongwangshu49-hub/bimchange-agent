"""Bounded IFC4 inspection and deterministic revision normalization."""

from __future__ import annotations

import hashlib
import io
import json
import re
from collections import Counter
from contextlib import redirect_stdout
from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any
from uuid import uuid4

import ifcopenshell
from ifcdiff import IfcDiff, __version__ as ifcdiff_version
from ifcopenshell.util.element import get_container
from jsonschema import Draft202012Validator

from . import __version__


SCHEMA_VERSION = "0.2.0-preview.1"
SCHEMA_URI = "bimchange-agent://schemas/product-change-record-0.2.0-preview.1"
PRODUCT_VERSION = __version__
RAW_DIFF_FILE_NAME = "ifcdiff.json"
CHANGE_RECORD_FILE_NAME = "change-records.json"
PROPERTY_PATH = re.compile(
    r"^root\['(?P<pset>(?:\\'|[^'])+)'\]\['(?P<name>(?:\\'|[^'])+)'\]$"
)
IFC_GUID = re.compile(r"^[0-3][0-9A-Za-z_$]{21}$")


class ProductBoundaryError(ValueError):
    """Raised when an input is outside the declared preview boundary."""


@dataclass(frozen=True)
class ProductLimits:
    """Conservative preview guards; these are not benchmark claims."""

    required_schema: str = "IFC4"
    max_file_mib: int = 50
    max_elements: int = 5_000
    min_shared_guid_ratio: float = 0.5

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mib * 1024 * 1024


DEFAULT_LIMITS = ProductLimits()


def sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file without loading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON object."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected a JSON object: {path}")
    return value


def _schema() -> dict[str, Any]:
    resource = files("bimchange_agent.resources").joinpath(
        "product-change-record.schema.json"
    )
    value = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("Packaged product schema is not a JSON object")
    return value


def validate_product_artifact(artifact: dict[str, Any]) -> None:
    """Validate a product Change Record artifact against its packaged schema."""
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(artifact)
    changes = artifact["changes"]
    unsupported = artifact["unsupported_changes"]
    summary = artifact["summary"]
    counts = Counter(change["change_type"] for change in changes)
    expected_summary = {
        "total_supported": len(changes),
        "added": counts["added"],
        "deleted": counts["deleted"],
        "property_modified": counts["property_modified"],
        "unsupported": len(unsupported),
    }
    if summary != expected_summary:
        raise ValueError("Artifact summary does not match its change records")
    change_ids = [change["change_id"] for change in changes]
    if len(change_ids) != len(set(change_ids)):
        raise ValueError("Artifact contains duplicate change_id values")
    for model_key in ("source", "revised"):
        file_name = artifact[model_key]["file_name"]
        if Path(file_name).name != file_name or "/" in file_name or "\\" in file_name:
            raise ValueError(f"Artifact {model_key} file_name must not contain a path")
    for change in changes:
        result_file = change["evidence"]["result_file"]
        if (
            Path(result_file).name != result_file
            or "/" in result_file
            or "\\" in result_file
        ):
            raise ValueError("Artifact evidence result_file must not contain a path")
        change_type = change["change_type"]
        if change_type == "added" and (
            change["old_value"] is not None or change["field"] is not None
        ):
            raise ValueError("Added records must have a null old_value and field")
        if change_type == "deleted" and (
            change["new_value"] is not None or change["field"] is not None
        ):
            raise ValueError("Deleted records must have a null new_value and field")
        if change_type == "property_modified" and change["field"] is None:
            raise ValueError("Property-modified records must identify a field")


def _require_ifc_path(path: Path, limits: ProductLimits) -> Path:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"IFC file not found: {path}")
    if path.suffix.lower() != ".ifc":
        raise ProductBoundaryError(f"Only .ifc files are supported: {path.name}")
    size = path.stat().st_size
    if size == 0:
        raise ProductBoundaryError(f"IFC file is empty: {path.name}")
    if size > limits.max_file_bytes:
        raise ProductBoundaryError(
            f"{path.name} is {size / 1024 / 1024:.1f} MiB; "
            f"the preview limit is {limits.max_file_mib} MiB"
        )
    return path


def _root_guid_diagnostics(
    model: ifcopenshell.file,
) -> tuple[set[str], int, int, int]:
    roots = [getattr(entity, "GlobalId", None) for entity in model.by_type("IfcRoot")]
    populated = [
        value
        for value in roots
        if isinstance(value, str) and IFC_GUID.fullmatch(value)
    ]
    invalid_count = len(roots) - len(populated)
    counts = Counter(populated)
    duplicate_count = sum(count - 1 for count in counts.values() if count > 1)
    elements = model.by_type("IfcElement")
    element_ids = {
        entity.GlobalId
        for entity in elements
        if isinstance(getattr(entity, "GlobalId", None), str)
        and IFC_GUID.fullmatch(entity.GlobalId)
    }
    return element_ids, duplicate_count, len(elements), invalid_count


def _inspect_loaded(
    path: Path,
    model: ifcopenshell.file,
    limits: ProductLimits,
    file_digest: str,
) -> tuple[dict[str, Any], set[str]]:
    element_ids, duplicate_count, element_count, invalid_guid_count = (
        _root_guid_diagnostics(model)
    )
    if model.schema != limits.required_schema:
        raise ProductBoundaryError(
            f"{path.name} uses {model.schema}; this preview supports only "
            f"{limits.required_schema}"
        )
    if invalid_guid_count:
        raise ProductBoundaryError(
            f"{path.name} contains {invalid_guid_count} IfcRoot objects with a missing "
            "or invalid GlobalId"
        )
    if not element_count:
        raise ProductBoundaryError(f"{path.name} contains no IfcElement objects")
    if element_count > limits.max_elements:
        raise ProductBoundaryError(
            f"{path.name} contains {element_count} IfcElement objects; "
            f"the preview limit is {limits.max_elements}"
        )
    if duplicate_count:
        raise ProductBoundaryError(
            f"{path.name} contains {duplicate_count} duplicate IfcRoot GlobalId values"
        )
    return (
        {
            "file_name": path.name,
            "sha256": file_digest,
            "file_size_bytes": path.stat().st_size,
            "ifc_schema": model.schema,
            "entity_count": sum(1 for _ in model),
            "element_count": element_count,
            "duplicate_root_guid_count": duplicate_count,
        },
        element_ids,
    )


def _open_stable_ifc(
    path: Path, limits: ProductLimits
) -> tuple[ifcopenshell.file, dict[str, Any], set[str]]:
    """Open and hash one IFC while rejecting concurrent file replacement/editing."""
    before = path.stat()
    signature_before = (
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
        getattr(before, "st_ino", 0),
    )
    try:
        model = ifcopenshell.open(path)
    except Exception as error:
        raise ProductBoundaryError(f"Could not open IFC file: {path.name}") from error
    file_digest = sha256(path)
    after = path.stat()
    signature_after = (
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
        getattr(after, "st_ino", 0),
    )
    if signature_before != signature_after:
        raise ProductBoundaryError(
            f"{path.name} changed while it was being read; choose the file again"
        )
    summary, element_ids = _inspect_loaded(path, model, limits, file_digest)
    return model, summary, element_ids


def inspect_ifc(
    path: Path,
    *,
    limits: ProductLimits = DEFAULT_LIMITS,
) -> dict[str, Any]:
    """Inspect one bounded IFC4 file for the future desktop application."""
    path = _require_ifc_path(path, limits)
    _, summary, _ = _open_stable_ifc(path, limits)
    return {
        "status": "PASS",
        "limits": asdict(limits),
        "model": summary,
        "model_calls_made": 0,
    }


def _entity_or_none(
    model: ifcopenshell.file, global_id: str
) -> ifcopenshell.entity_instance | None:
    try:
        return model.by_guid(global_id)
    except RuntimeError:
        return None


def _reference(
    entity: ifcopenshell.entity_instance | None,
) -> dict[str, Any] | None:
    if entity is None:
        return None
    global_id = getattr(entity, "GlobalId", None)
    if not isinstance(global_id, str) or not global_id:
        return None
    return {
        "entity_type": entity.is_a(),
        "global_id": global_id,
        "name": getattr(entity, "Name", None),
    }


def _location(element: ifcopenshell.entity_instance) -> dict[str, Any]:
    container = get_container(element)
    storey = container if container is not None and container.is_a(
        "IfcBuildingStorey"
    ) else None
    return {
        "spatial_container": _reference(container),
        "building_storey": _reference(storey),
    }


def _snapshot(element: ifcopenshell.entity_instance) -> dict[str, Any]:
    return {
        "name": getattr(element, "Name", None),
        "tag": getattr(element, "Tag", None),
        "predefined_type": getattr(element, "PredefinedType", None),
    }


def _change_id(*parts: str) -> str:
    material = "\x1f".join(parts).encode("utf-8")
    return f"chg-{hashlib.sha256(material).hexdigest()[:16]}"


def _base_record(
    change_type: str,
    global_id: str,
    element: ifcopenshell.entity_instance,
    *,
    raw_diff_name: str,
    selector: str,
) -> dict[str, Any]:
    return {
        "change_id": _change_id(change_type, global_id, selector),
        "change_type": change_type,
        "entity_type": element.is_a(),
        "global_id": global_id,
        "location": _location(element),
        "field": None,
        "old_value": None,
        "new_value": None,
        "evidence": {
            "reference_source": "ifcdiff",
            "detector": f"IfcDiff {ifcdiff_version}",
            "result_file": raw_diff_name,
            "selector": selector,
        },
    }


def _parse_property_path(path: str) -> tuple[str, str] | None:
    match = PROPERTY_PATH.fullmatch(path)
    if match is None:
        return None
    return (
        match.group("pset").replace("\\'", "'"),
        match.group("name").replace("\\'", "'"),
    )


def _normalize_diff(
    raw: dict[str, Any],
    old_model: ifcopenshell.file,
    new_model: ifcopenshell.file,
    *,
    raw_diff_name: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    records: list[dict[str, Any]] = []
    unsupported: list[dict[str, str]] = []

    for global_id in sorted(raw.get("added", [])):
        entity = _entity_or_none(new_model, global_id)
        if entity is None:
            unsupported.append(
                {
                    "global_id": global_id,
                    "reason": "IfcDiff reported an addition missing from the revised model",
                    "selector": "added",
                }
            )
            continue
        if not entity.is_a("IfcElement"):
            unsupported.append(
                {
                    "global_id": global_id,
                    "reason": "Added entity is not an IfcElement",
                    "selector": "added",
                }
            )
            continue
        record = _base_record(
            "added", global_id, entity, raw_diff_name=raw_diff_name, selector="added"
        )
        record["new_value"] = _snapshot(entity)
        records.append(record)

    for global_id in sorted(raw.get("deleted", [])):
        entity = _entity_or_none(old_model, global_id)
        if entity is None:
            unsupported.append(
                {
                    "global_id": global_id,
                    "reason": "IfcDiff reported a deletion missing from the source model",
                    "selector": "deleted",
                }
            )
            continue
        if not entity.is_a("IfcElement"):
            unsupported.append(
                {
                    "global_id": global_id,
                    "reason": "Deleted entity is not an IfcElement",
                    "selector": "deleted",
                }
            )
            continue
        record = _base_record(
            "deleted",
            global_id,
            entity,
            raw_diff_name=raw_diff_name,
            selector="deleted",
        )
        record["old_value"] = _snapshot(entity)
        records.append(record)

    changed = raw.get("changed", {})
    if not isinstance(changed, dict):
        raise ProductBoundaryError("IfcDiff returned a non-object changed section")
    for global_id in sorted(changed):
        flags = changed[global_id]
        if not isinstance(flags, dict):
            unsupported.append(
                {
                    "global_id": global_id,
                    "reason": "IfcDiff change flags are not an object",
                    "selector": f"changed.{global_id}",
                }
            )
            continue
        for flag in sorted(set(flags) - {"properties_changed"}):
            unsupported.append(
                {
                    "global_id": global_id,
                    "reason": f"IfcDiff flag is outside the preview boundary: {flag}",
                    "selector": f"changed.{global_id}.{flag}",
                }
            )
        property_diff = flags.get("properties_changed")
        if not isinstance(property_diff, dict):
            if property_diff is not None:
                unsupported.append(
                    {
                        "global_id": global_id,
                        "reason": "Property difference has no structured value details",
                        "selector": f"changed.{global_id}.properties_changed",
                    }
                )
            continue
        values_changed = property_diff.get("values_changed", {})
        if not isinstance(values_changed, dict):
            values_changed = {}
        entity = _entity_or_none(new_model, global_id) or _entity_or_none(
            old_model, global_id
        )
        if entity is None:
            unsupported.append(
                {
                    "global_id": global_id,
                    "reason": "Changed entity is missing from both models",
                    "selector": f"changed.{global_id}",
                }
            )
            continue
        if not entity.is_a("IfcElement"):
            unsupported.append(
                {
                    "global_id": global_id,
                    "reason": "Changed entity is not an IfcElement",
                    "selector": f"changed.{global_id}",
                }
            )
            continue
        for path, values in sorted(values_changed.items()):
            parsed = _parse_property_path(path)
            if (
                parsed is None
                or not isinstance(values, dict)
                or "old_value" not in values
                or "new_value" not in values
            ):
                unsupported.append(
                    {
                        "global_id": global_id,
                        "reason": "Property path or value payload is outside the preview boundary",
                        "selector": (
                            f"changed.{global_id}.properties_changed.values_changed.{path}"
                        ),
                    }
                )
                continue
            try:
                json.dumps(
                    {"old_value": values["old_value"], "new_value": values["new_value"]}
                )
            except (TypeError, ValueError):
                unsupported.append(
                    {
                        "global_id": global_id,
                        "reason": "Property values are not JSON serializable",
                        "selector": (
                            f"changed.{global_id}.properties_changed.values_changed.{path}"
                        ),
                    }
                )
                continue
            property_set, property_name = parsed
            selector = (
                f"changed.{global_id}.properties_changed.values_changed.{path}"
            )
            record = _base_record(
                "property_modified",
                global_id,
                entity,
                raw_diff_name=raw_diff_name,
                selector=selector,
            )
            record["change_id"] = _change_id(
                "property_modified", global_id, property_set, property_name
            )
            record["field"] = {
                "kind": "property",
                "property_set": property_set,
                "name": property_name,
            }
            record["old_value"] = values.get("old_value")
            record["new_value"] = values.get("new_value")
            records.append(record)
        for category in sorted(set(property_diff) - {"values_changed"}):
            unsupported.append(
                {
                    "global_id": global_id,
                    "reason": (
                        "Property difference category is outside the preview boundary: "
                        f"{category}"
                    ),
                    "selector": f"changed.{global_id}.properties_changed.{category}",
                }
            )

    records.sort(key=lambda item: item["change_id"])
    unsupported.sort(key=lambda item: (item["global_id"], item["selector"]))
    return records, unsupported


def _write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        temporary.replace(path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def diff_ifc_pair(
    source_path: Path,
    revised_path: Path,
    output_dir: Path,
    *,
    limits: ProductLimits = DEFAULT_LIMITS,
) -> dict[str, Any]:
    """Diff a bounded IFC4 pair and emit raw plus normalized JSON artifacts."""
    source_path = _require_ifc_path(source_path, limits)
    revised_path = _require_ifc_path(revised_path, limits)
    source_model, source_summary, source_ids = _open_stable_ifc(source_path, limits)
    revised_model, revised_summary, revised_ids = _open_stable_ifc(
        revised_path, limits
    )

    denominator = min(len(source_ids), len(revised_ids))
    shared_count = len(source_ids & revised_ids)
    shared_ratio = shared_count / denominator if denominator else 0.0
    if shared_ratio < limits.min_shared_guid_ratio:
        raise ProductBoundaryError(
            f"Only {shared_ratio:.1%} of comparable element GUIDs are shared; "
            f"the preview requires at least {limits.min_shared_guid_ratio:.0%}. "
            "The files may come from unrelated models or an export that regenerated GUIDs."
        )

    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_diff_path = output_dir / RAW_DIFF_FILE_NAME
    records_path = output_dir / CHANGE_RECORD_FILE_NAME
    existing = [path.name for path in (raw_diff_path, records_path) if path.exists()]
    if existing:
        raise ProductBoundaryError(
            "Output directory already contains product artifacts: " + ", ".join(existing)
        )

    detector = IfcDiff(
        source_model,
        revised_model,
        relationships=["property"],
        is_shallow=False,
    )
    temporary_raw_path = raw_diff_path.with_name(
        f".{raw_diff_path.name}.{uuid4().hex}.tmp"
    )
    try:
        with redirect_stdout(io.StringIO()):
            detector.diff()
            detector.export(str(temporary_raw_path))
        raw = load_json(temporary_raw_path)
        temporary_raw_path.replace(raw_diff_path)
    except Exception as error:
        raise ProductBoundaryError("IfcDiff could not compare this IFC pair") from error
    finally:
        try:
            temporary_raw_path.unlink(missing_ok=True)
        except OSError:
            pass
    records, unsupported = _normalize_diff(
        raw,
        source_model,
        revised_model,
        raw_diff_name=raw_diff_path.name,
    )
    counts = Counter(record["change_type"] for record in records)
    warnings = [
        "Preview scope: IFC4 only; supported changes are added, deleted, and property value modifications.",
        "Results rely on stable IFC GlobalId values and are not engineering or safety conclusions.",
    ]
    if shared_ratio < 0.8:
        warnings.append(
            "The shared element GUID ratio is below 80%; review added/deleted counts carefully."
        )
    if unsupported:
        warnings.append(
            "IfcDiff reported changes outside the preview normalization boundary; see unsupported_changes."
        )
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "schema": SCHEMA_URI,
        "generator": {
            "name": "BIMChange-Agent",
            "version": PRODUCT_VERSION,
            "detector": f"IfcDiff {ifcdiff_version}",
            "relationships": ["property"],
        },
        "limits": asdict(limits),
        "source": source_summary,
        "revised": revised_summary,
        "pair_diagnostics": {
            "shared_element_guid_count": shared_count,
            "shared_element_guid_ratio": round(shared_ratio, 6),
        },
        "summary": {
            "total_supported": len(records),
            "added": counts["added"],
            "deleted": counts["deleted"],
            "property_modified": counts["property_modified"],
            "unsupported": len(unsupported),
        },
        "warnings": warnings,
        "changes": records,
        "unsupported_changes": unsupported,
        "model_calls_made": 0,
    }
    validate_product_artifact(artifact)
    _write_json(records_path, artifact)
    return {
        "status": "PASS_WITH_UNSUPPORTED_CHANGES" if unsupported else "PASS",
        "output_dir": str(output_dir),
        "raw_diff": str(raw_diff_path),
        "change_records": str(records_path),
        "summary": artifact["summary"],
        "model_calls_made": 0,
    }
