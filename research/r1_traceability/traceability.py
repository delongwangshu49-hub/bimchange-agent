"""Deterministic R1 evidence-manifest generation and fail-closed verification."""

from __future__ import annotations

import hashlib
import io
import json
import re
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

import ifcopenshell
from ifcdiff import IfcDiff, __version__ as ifcdiff_version
from ifcopenshell.util.element import get_container, get_pset
from jsonschema import Draft202012Validator

from bimchange_agent.product_core import validate_product_artifact


PROTOCOL_ID = "r1-traceability-0.1.0"
MANIFEST_SCHEMA_VERSION = "0.1.0"
MANIFEST_FILE_NAME = "trace-manifest.json"
EXPECTED_DETECTOR = {
    "name": "IfcDiff",
    "version": "0.8.5",
    "configuration": {"relationships": ["property"], "is_shallow": False},
    "verification": "reexecute_and_compare_canonical_result",
}
NORMALIZATION_RULES = {
    "added": "normalize-added-v1",
    "deleted": "normalize-deleted-v1",
    "property_modified": "normalize-property-value-v1",
}
DERIVED_FIELDS = (
    "change_type",
    "entity_type",
    "global_id",
    "location",
    "field",
    "old_value",
    "new_value",
)
PROPERTY_PATH = re.compile(
    r"^root\['(?P<pset>(?:\\'|[^'])+)'\]\['(?P<name>(?:\\'|[^'])+)'\]$"
)
WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
UNC_ABSOLUTE = re.compile(r"^\\\\")
CREDENTIAL_TEXT = re.compile(
    r"(?i)(?:api[_ -]?key|access[_ -]?token|secret)\s*[:=]|sk-[A-Za-z0-9_-]{12,}"
)


class TraceabilityError(ValueError):
    """One fail-closed traceability diagnostic."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class DuplicateJsonKeyError(ValueError):
    """Raised when strict JSON loading observes a duplicate object key."""


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(f"Duplicate JSON object key: {key}")
        result[key] = value
    return result


def strict_load_json(path: Path) -> dict[str, Any]:
    """Load one JSON object while rejecting duplicate keys and non-finite values."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"Non-finite JSON number is not allowed: {value}")

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
            parse_constant=reject_constant,
        )
    except DuplicateJsonKeyError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"Invalid JSON object: {path.name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path.name}")
    return value


def _load_stable_json(path: Path) -> tuple[dict[str, Any], str, str]:
    """Load, hash, and canonicalize JSON while rejecting a concurrent rewrite."""
    before = _file_signature(path)
    value = strict_load_json(path)
    file_digest = sha256_file(path)
    canonical_digest = digest_value(value)
    after = _file_signature(path)
    if before != after:
        raise TraceabilityError(
            "input_changed_during_read", f"JSON changed while being read: {path.name}"
        )
    return value, file_digest, canonical_digest


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    """Atomically write stable, readable JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(
                value,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _file_signature(path: Path) -> tuple[int, int, int, int]:
    stat = path.stat()
    return (
        stat.st_size,
        stat.st_mtime_ns,
        stat.st_ctime_ns,
        getattr(stat, "st_ino", 0),
    )


def _open_stable_ifc(path: Path) -> tuple[ifcopenshell.file, str]:
    before = _file_signature(path)
    digest_before = sha256_file(path)
    try:
        model = ifcopenshell.open(path)
    except Exception as error:
        raise TraceabilityError(
            "global_id_resolution_failure", f"Could not open IFC role input: {path.name}"
        ) from error
    digest_after = sha256_file(path)
    after = _file_signature(path)
    if before != after or digest_before != digest_after:
        raise TraceabilityError(
            "input_changed_during_read", f"IFC changed while being read: {path.name}"
        )
    return model, digest_before


def _manifest_schema() -> dict[str, Any]:
    return strict_load_json(Path(__file__).with_name("trace-manifest.schema.json"))


def _reference(entity: ifcopenshell.entity_instance | None) -> dict[str, Any] | None:
    if entity is None:
        return None
    return {
        "entity_type": entity.is_a(),
        "global_id": entity.GlobalId,
        "name": getattr(entity, "Name", None),
    }


def _location(element: ifcopenshell.entity_instance) -> dict[str, Any]:
    container = get_container(element)
    storey = (
        container
        if container is not None and container.is_a("IfcBuildingStorey")
        else None
    )
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


def _guid_matches(
    model: ifcopenshell.file, global_id: str
) -> list[ifcopenshell.entity_instance]:
    return [
        entity
        for entity in model.by_type("IfcRoot")
        if getattr(entity, "GlobalId", None) == global_id
    ]


def _parse_property_path(path: str) -> tuple[str, str]:
    match = PROPERTY_PATH.fullmatch(path)
    if match is None:
        raise TraceabilityError(
            "evidence_locator_missing", "Property path is outside the frozen grammar"
        )
    return (
        match.group("pset").replace("\\'", "'"),
        match.group("name").replace("\\'", "'"),
    )


def _raw_selected_value(
    raw: dict[str, Any], locator: dict[str, Any]
) -> tuple[Any, int]:
    section = locator["section"]
    global_id = locator["global_id"]
    property_path = locator["property_path"]
    if section in {"added", "deleted"}:
        values = raw.get(section)
        if not isinstance(values, list):
            raise TraceabilityError(
                "evidence_locator_missing", f"Raw {section} section is not an array"
            )
        match_count = values.count(global_id)
        if match_count == 0:
            raise TraceabilityError(
                "evidence_locator_missing", f"GlobalId is absent from raw {section}"
            )
        if match_count != 1:
            raise TraceabilityError(
                "evidence_locator_ambiguous", f"GlobalId repeats in raw {section}"
            )
        if property_path is not None:
            raise TraceabilityError(
                "evidence_locator_missing", f"Raw {section} locator has a property path"
            )
        return global_id, match_count
    if section != "changed" or not isinstance(property_path, str):
        raise TraceabilityError(
            "evidence_locator_missing", "Property modification locator is incomplete"
        )
    changed = raw.get("changed")
    if not isinstance(changed, dict) or global_id not in changed:
        raise TraceabilityError(
            "evidence_locator_missing", "GlobalId is absent from raw changed section"
        )
    flags = changed[global_id]
    try:
        selected = flags["properties_changed"]["values_changed"][property_path]
    except (KeyError, TypeError) as error:
        raise TraceabilityError(
            "evidence_locator_missing", "Property path is absent from raw changed entry"
        ) from error
    if not isinstance(selected, dict) or not {"old_value", "new_value"} <= set(
        selected
    ):
        raise TraceabilityError(
            "evidence_locator_missing", "Selected property leaf has no old/new values"
        )
    return selected, 1


def _expected_locator(record: dict[str, Any]) -> dict[str, Any]:
    change_type = record["change_type"]
    if change_type == "added":
        return {
            "section": "added",
            "global_id": record["global_id"],
            "property_path": None,
        }
    if change_type == "deleted":
        return {
            "section": "deleted",
            "global_id": record["global_id"],
            "property_path": None,
        }
    if change_type != "property_modified":
        raise TraceabilityError(
            "unsupported_change_type", f"Unsupported change type: {change_type}"
        )
    field = record.get("field")
    if not isinstance(field, dict) or field.get("kind") != "property":
        raise TraceabilityError(
            "evidence_locator_missing", "Property-modified record has no property field"
        )
    evidence = record.get("evidence")
    selector = evidence.get("selector") if isinstance(evidence, dict) else None
    prefix = (
        f"changed.{record['global_id']}.properties_changed.values_changed."
    )
    if not isinstance(selector, str) or not selector.startswith(prefix):
        raise TraceabilityError(
            "evidence_locator_missing", "Property selector has no frozen raw-path prefix"
        )
    property_path = selector[len(prefix) :]
    property_set, property_name = _parse_property_path(property_path)
    if (
        property_set != field.get("property_set")
        or property_name != field.get("name")
    ):
        raise TraceabilityError(
            "evidence_locator_missing",
            "Property selector path differs from the structured Change Record field",
        )
    return {
        "section": "changed",
        "global_id": record["global_id"],
        "property_path": property_path,
    }


def _require_one_element(
    model: ifcopenshell.file, global_id: str, *, role: str
) -> ifcopenshell.entity_instance:
    matches = _guid_matches(model, global_id)
    if len(matches) != 1 or not matches[0].is_a("IfcElement"):
        raise TraceabilityError(
            "global_id_resolution_failure",
            f"{global_id} does not resolve to exactly one IfcElement in {role}",
        )
    return matches[0]


def _require_absent(model: ifcopenshell.file, global_id: str, *, role: str) -> None:
    if _guid_matches(model, global_id):
        raise TraceabilityError(
            "global_id_resolution_failure", f"{global_id} unexpectedly exists in {role}"
        )


def _reconstruct_facts(
    record: dict[str, Any],
    raw: dict[str, Any],
    source_model: ifcopenshell.file,
    revised_model: ifcopenshell.file,
    *,
    locator: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], Any, int]:
    locator = locator or _expected_locator(record)
    selected, match_count = _raw_selected_value(raw, locator)
    global_id = locator["global_id"]
    change_type = record["change_type"]
    if change_type == "added":
        if locator["section"] != "added" or global_id != record["global_id"]:
            raise TraceabilityError("evidence_locator_missing", "Added locator drifted")
        _require_absent(source_model, global_id, role="source")
        entity = _require_one_element(revised_model, global_id, role="revised")
        facts = {
            "change_type": "added",
            "entity_type": entity.is_a(),
            "global_id": global_id,
            "location": _location(entity),
            "field": None,
            "old_value": None,
            "new_value": _snapshot(entity),
        }
    elif change_type == "deleted":
        if locator["section"] != "deleted" or global_id != record["global_id"]:
            raise TraceabilityError("evidence_locator_missing", "Deleted locator drifted")
        entity = _require_one_element(source_model, global_id, role="source")
        _require_absent(revised_model, global_id, role="revised")
        facts = {
            "change_type": "deleted",
            "entity_type": entity.is_a(),
            "global_id": global_id,
            "location": _location(entity),
            "field": None,
            "old_value": _snapshot(entity),
            "new_value": None,
        }
    elif change_type == "property_modified":
        if locator["section"] != "changed" or global_id != record["global_id"]:
            raise TraceabilityError(
                "evidence_locator_missing", "Property locator identity drifted"
            )
        property_set, property_name = _parse_property_path(locator["property_path"])
        source_entity = _require_one_element(source_model, global_id, role="source")
        revised_entity = _require_one_element(revised_model, global_id, role="revised")
        if source_entity.is_a() != revised_entity.is_a():
            raise TraceabilityError(
                "global_id_resolution_failure", "Entity type changed across property evidence"
            )
        source_value = get_pset(source_entity, property_set, property_name)
        revised_value = get_pset(revised_entity, property_set, property_name)
        if (
            source_value != selected["old_value"]
            or revised_value != selected["new_value"]
        ):
            raise TraceabilityError(
                "raw_value_mismatch", "Raw property values do not match both IFC models"
            )
        facts = {
            "change_type": "property_modified",
            "entity_type": revised_entity.is_a(),
            "global_id": global_id,
            "location": _location(revised_entity),
            "field": {
                "kind": "property",
                "property_set": property_set,
                "name": property_name,
            },
            "old_value": selected["old_value"],
            "new_value": selected["new_value"],
        }
    else:
        raise TraceabilityError(
            "unsupported_change_type", f"Unsupported change type: {change_type}"
        )
    return facts, selected, match_count


def _record_facts(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record.get(key) for key in DERIVED_FIELDS}


def _trace_id(entry_without_id: dict[str, Any]) -> str:
    material = {"protocol_id": PROTOCOL_ID, **entry_without_id}
    return f"trace-{digest_value(material)[:24]}"


def _expected_selector(record: dict[str, Any], locator: dict[str, Any]) -> str:
    if record["change_type"] in {"added", "deleted"}:
        return record["change_type"]
    return (
        f"changed.{record['global_id']}.properties_changed.values_changed."
        f"{locator['property_path']}"
    )


def _check_product_evidence(record: dict[str, Any], locator: dict[str, Any]) -> None:
    evidence = record.get("evidence")
    if not isinstance(evidence, dict):
        raise TraceabilityError(
            "change_record_digest_mismatch", "Change Record has no evidence object"
        )
    if evidence.get("result_file") != "ifcdiff.json":
        raise TraceabilityError(
            "privacy_boundary_violation", "Change Record result_file is not a role basename"
        )
    if evidence.get("selector") != _expected_selector(record, locator):
        raise TraceabilityError(
            "evidence_locator_missing", "Legacy Change Record selector drifted"
        )
    if evidence.get("detector") != "IfcDiff 0.8.5":
        raise TraceabilityError(
            "detector_configuration_mismatch", "Change Record detector text drifted"
        )


def _artifact_binding(
    role_name: str, file_digest: str, canonical_digest: str
) -> dict[str, str]:
    return {
        "role_name": role_name,
        "sha256": file_digest,
        "canonical_json_sha256": canonical_digest,
    }


def generate_trace_manifest(
    source_path: Path,
    revised_path: Path,
    change_records_path: Path,
    raw_result_path: Path,
) -> dict[str, Any]:
    """Generate a deterministic manifest without persisting real input paths."""
    source_path = Path(source_path).resolve()
    revised_path = Path(revised_path).resolve()
    change_records_path = Path(change_records_path).resolve()
    raw_result_path = Path(raw_result_path).resolve()
    try:
        records_artifact, records_file_digest, records_canonical_digest = (
            _load_stable_json(change_records_path)
        )
        raw, raw_file_digest, raw_canonical_digest = _load_stable_json(
            raw_result_path
        )
    except DuplicateJsonKeyError as error:
        raise TraceabilityError("raw_result_duplicate_key", str(error)) from error
    validate_product_artifact(records_artifact)
    source_model, source_digest = _open_stable_ifc(source_path)
    revised_model, revised_digest = _open_stable_ifc(revised_path)
    if source_digest != records_artifact["source"]["sha256"]:
        raise TraceabilityError("input_hash_mismatch", "Product source digest drifted")
    if revised_digest != records_artifact["revised"]["sha256"]:
        raise TraceabilityError("input_hash_mismatch", "Product revised digest drifted")
    generator = records_artifact["generator"]
    if (
        generator.get("detector") != "IfcDiff 0.8.5"
        or generator.get("relationships") != ["property"]
        or ifcdiff_version != "0.8.5"
    ):
        raise TraceabilityError(
            "detector_configuration_mismatch", "Product detector metadata is not frozen"
        )

    entries: list[dict[str, Any]] = []
    for record in sorted(records_artifact["changes"], key=lambda item: item["change_id"]):
        locator = _expected_locator(record)
        _check_product_evidence(record, locator)
        facts, selected, match_count = _reconstruct_facts(
            record, raw, source_model, revised_model, locator=locator
        )
        if _record_facts(record) != facts:
            raise TraceabilityError(
                "derived_fields_mismatch", "Change Record differs from reconstructed facts"
            )
        entry_without_id = {
            "change_id": record["change_id"],
            "change_record_sha256": digest_value(record),
            "global_id": record["global_id"],
            "change_type": record["change_type"],
            "raw_evidence": {
                "locator": locator,
                "selected_value_sha256": digest_value(selected),
            },
            "normalization": {
                "rule_id": NORMALIZATION_RULES[record["change_type"]],
                "decision": "supported",
                "derived_fields_sha256": digest_value(facts),
            },
            "resolution": {"status": "resolved_unique", "match_count": match_count},
        }
        entries.append({"trace_id": _trace_id(entry_without_id), **entry_without_id})

    supported_types = sorted({entry["change_type"] for entry in entries})
    total = len(records_artifact["changes"])
    resolved = len(entries)
    manifest = {
        "protocol_id": PROTOCOL_ID,
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "artifacts": {
            "source": {"role_name": "source.ifc", "sha256": source_digest},
            "revised": {"role_name": "revised.ifc", "sha256": revised_digest},
            "change_records": _artifact_binding(
                "change-records.json", records_file_digest, records_canonical_digest
            ),
            "raw_result": _artifact_binding(
                "ifcdiff.json", raw_file_digest, raw_canonical_digest
            ),
        },
        "detector": EXPECTED_DETECTOR,
        "normalization_rules": NORMALIZATION_RULES,
        "entries": entries,
        "summary": {
            "supported_change_records": total,
            "resolved_unique": resolved,
            "trace_resolution_rate": resolved / total if total else 1.0,
            "supported_change_types": supported_types,
        },
        "model_calls_made": 0,
    }
    schema = _manifest_schema()
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(manifest)
    violations = privacy_violations(manifest)
    if violations:
        raise TraceabilityError(
            "privacy_boundary_violation", "; ".join(violations)
        )
    return manifest


def _walk_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def privacy_violations(manifest: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    for value in _walk_strings(manifest):
        if WINDOWS_ABSOLUTE.match(value) or UNC_ABSOLUTE.match(value) or value.startswith("/"):
            violations.append("absolute_path")
        if CREDENTIAL_TEXT.search(value):
            violations.append("credential_pattern")
    expected_roles = {
        "source": "source.ifc",
        "revised": "revised.ifc",
        "change_records": "change-records.json",
        "raw_result": "ifcdiff.json",
    }
    artifacts = manifest.get("artifacts")
    if isinstance(artifacts, dict):
        for key, role in expected_roles.items():
            if not isinstance(artifacts.get(key), dict) or artifacts[key].get(
                "role_name"
            ) != role:
                violations.append(f"role_alias:{key}")
    return sorted(set(violations))


def _reexecute_detector(
    source_model: ifcopenshell.file, revised_model: ifcopenshell.file
) -> dict[str, Any]:
    detector = IfcDiff(
        source_model,
        revised_model,
        relationships=["property"],
        is_shallow=False,
    )
    with tempfile.TemporaryDirectory(prefix="bimchange-r1-") as directory:
        path = Path(directory) / "ifcdiff.json"
        with redirect_stdout(io.StringIO()):
            detector.diff()
            detector.export(str(path))
        try:
            return strict_load_json(path)
        except DuplicateJsonKeyError as error:
            raise TraceabilityError("raw_result_duplicate_key", str(error)) from error


def _require_equal(actual: Any, expected: Any, code: str, message: str) -> None:
    if actual != expected:
        raise TraceabilityError(code, message)


def _verify_or_raise(
    manifest_path: Path,
    source_path: Path,
    revised_path: Path,
    change_records_path: Path,
    raw_result_path: Path,
) -> dict[str, Any]:
    try:
        manifest, _, _ = _load_stable_json(manifest_path)
    except DuplicateJsonKeyError as error:
        raise TraceabilityError("raw_result_duplicate_key", str(error)) from error
    violations = privacy_violations(manifest)
    if violations:
        raise TraceabilityError(
            "privacy_boundary_violation", "; ".join(violations)
        )
    schema = _manifest_schema()
    errors = sorted(Draft202012Validator(schema).iter_errors(manifest), key=str)
    if errors:
        raise TraceabilityError("manifest_schema_invalid", errors[0].message)
    _require_equal(
        manifest["detector"],
        EXPECTED_DETECTOR,
        "detector_configuration_mismatch",
        "Manifest detector metadata differs from the frozen configuration",
    )
    _require_equal(
        ifcdiff_version,
        "0.8.5",
        "detector_configuration_mismatch",
        "Installed IfcDiff version differs from the frozen version",
    )
    _require_equal(
        manifest["normalization_rules"],
        NORMALIZATION_RULES,
        "normalization_rule_mismatch",
        "Manifest normalization rule registry drifted",
    )

    try:
        records_artifact, records_file_digest, records_canonical_digest = (
            _load_stable_json(change_records_path)
        )
        raw, raw_file_digest, raw_canonical_digest = _load_stable_json(
            raw_result_path
        )
    except DuplicateJsonKeyError as error:
        raise TraceabilityError("raw_result_duplicate_key", str(error)) from error
    try:
        validate_product_artifact(records_artifact)
    except Exception as error:
        raise TraceabilityError(
            "change_record_digest_mismatch", "Product Change Record artifact is invalid"
        ) from error
    source_model, source_digest = _open_stable_ifc(source_path)
    revised_model, revised_digest = _open_stable_ifc(revised_path)
    artifacts = manifest["artifacts"]
    _require_equal(
        source_digest,
        artifacts["source"]["sha256"],
        "input_hash_mismatch",
        "Source IFC digest differs from the manifest",
    )
    _require_equal(
        revised_digest,
        artifacts["revised"]["sha256"],
        "input_hash_mismatch",
        "Revised IFC digest differs from the manifest",
    )
    _require_equal(
        records_artifact["source"]["sha256"],
        source_digest,
        "input_hash_mismatch",
        "Change Record source digest differs from the actual IFC",
    )
    _require_equal(
        records_artifact["revised"]["sha256"],
        revised_digest,
        "input_hash_mismatch",
        "Change Record revised digest differs from the actual IFC",
    )
    _require_equal(
        records_file_digest,
        artifacts["change_records"]["sha256"],
        "change_record_digest_mismatch",
        "Change Record file digest differs from the manifest",
    )
    _require_equal(
        records_canonical_digest,
        artifacts["change_records"]["canonical_json_sha256"],
        "change_record_digest_mismatch",
        "Change Record semantic digest differs from the manifest",
    )
    _require_equal(
        raw_file_digest,
        artifacts["raw_result"]["sha256"],
        "raw_result_hash_mismatch",
        "Raw IfcDiff file digest differs from the manifest",
    )
    _require_equal(
        raw_canonical_digest,
        artifacts["raw_result"]["canonical_json_sha256"],
        "raw_result_canonical_hash_mismatch",
        "Raw IfcDiff semantic digest differs from the manifest",
    )
    generator = records_artifact["generator"]
    if (
        generator.get("detector") != "IfcDiff 0.8.5"
        or generator.get("relationships") != ["property"]
    ):
        raise TraceabilityError(
            "detector_configuration_mismatch", "Product generator metadata drifted"
        )
    replay = _reexecute_detector(source_model, revised_model)
    _require_equal(
        replay,
        raw,
        "raw_result_reproduction_mismatch",
        "Re-executed IfcDiff result differs from the registered raw result",
    )

    records = records_artifact["changes"]
    entries = manifest["entries"]
    if len({record["change_id"] for record in records}) != len(records):
        raise TraceabilityError(
            "change_record_digest_mismatch", "Duplicate Change Record change_id"
        )
    entry_by_id = {entry["change_id"]: entry for entry in entries}
    if len(entry_by_id) != len(entries) or set(entry_by_id) != {
        record["change_id"] for record in records
    }:
        raise TraceabilityError(
            "change_record_digest_mismatch", "Manifest entry set differs from Change Records"
        )
    resolved = 0
    for record in sorted(records, key=lambda item: item["change_id"]):
        entry = entry_by_id[record["change_id"]]
        if entry["change_type"] not in NORMALIZATION_RULES:
            raise TraceabilityError(
                "unsupported_change_type", "Manifest entry has an unsupported change type"
            )
        if entry["global_id"] != record["global_id"]:
            raise TraceabilityError(
                "global_id_resolution_failure", "Manifest and Change Record GlobalId differ"
            )
        _require_equal(
            entry["change_type"],
            record["change_type"],
            "unsupported_change_type",
            "Manifest and Change Record change type differ",
        )
        _require_equal(
            entry["change_record_sha256"],
            digest_value(record),
            "change_record_digest_mismatch",
            "Per-record digest differs from the Change Record",
        )
        locator = entry["raw_evidence"]["locator"]
        _check_product_evidence(record, locator)
        facts, selected, match_count = _reconstruct_facts(
            record, raw, source_model, revised_model, locator=locator
        )
        _require_equal(
            _record_facts(record),
            facts,
            "derived_fields_mismatch",
            "Change Record facts differ from independent reconstruction",
        )
        _require_equal(
            entry["raw_evidence"]["selected_value_sha256"],
            digest_value(selected),
            "raw_value_mismatch",
            "Selected raw evidence digest differs",
        )
        _require_equal(
            entry["normalization"]["rule_id"],
            NORMALIZATION_RULES[record["change_type"]],
            "normalization_rule_mismatch",
            "Entry normalization rule differs from the frozen registry",
        )
        _require_equal(
            entry["normalization"]["derived_fields_sha256"],
            digest_value(facts),
            "derived_fields_mismatch",
            "Derived factual-field digest differs",
        )
        _require_equal(
            entry["resolution"],
            {"status": "resolved_unique", "match_count": match_count},
            "evidence_locator_ambiguous",
            "Entry resolution status is not uniquely resolved",
        )
        entry_without_id = {key: value for key, value in entry.items() if key != "trace_id"}
        _require_equal(
            entry["trace_id"],
            _trace_id(entry_without_id),
            "change_record_digest_mismatch",
            "Trace identifier differs from its bound evidence",
        )
        resolved += 1

    expected_types = sorted({record["change_type"] for record in records})
    total = len(records)
    expected_summary = {
        "supported_change_records": total,
        "resolved_unique": resolved,
        "trace_resolution_rate": resolved / total if total else 1.0,
        "supported_change_types": expected_types,
    }
    _require_equal(
        manifest["summary"],
        expected_summary,
        "derived_fields_mismatch",
        "Manifest summary differs from verified entries",
    )
    return {
        "status": "PASS",
        "protocol_id": PROTOCOL_ID,
        "supported_change_records": total,
        "resolved_unique": resolved,
        "trace_resolution_rate": expected_summary["trace_resolution_rate"],
        "supported_change_types": expected_types,
        "privacy_violation_count": 0,
        "failures": [],
        "model_calls_made": 0,
    }


def verify_trace_manifest(
    manifest_path: Path,
    source_path: Path,
    revised_path: Path,
    change_records_path: Path,
    raw_result_path: Path,
) -> dict[str, Any]:
    """Verify a manifest and return one stable PASS/FAIL report."""
    try:
        return _verify_or_raise(
            Path(manifest_path).resolve(),
            Path(source_path).resolve(),
            Path(revised_path).resolve(),
            Path(change_records_path).resolve(),
            Path(raw_result_path).resolve(),
        )
    except TraceabilityError as error:
        return {
            "status": "FAIL",
            "protocol_id": PROTOCOL_ID,
            "failures": [{"code": error.code, "message": str(error)}],
            "model_calls_made": 0,
        }
    except Exception as error:
        return {
            "status": "FAIL",
            "protocol_id": PROTOCOL_ID,
            "failures": [
                {
                    "code": "unexpected_validation_failure",
                    "message": f"{type(error).__name__}: {error}",
                }
            ],
            "model_calls_made": 0,
        }
