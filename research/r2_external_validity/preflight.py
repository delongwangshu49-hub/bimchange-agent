"""Privacy-preserving preflight for authorised local IFC research samples."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import uuid4

import ifcopenshell


PROTOCOL_ID = "r2-external-validity-0.1.0"
IFC_GUID = re.compile(r"^[0-3][0-9A-Za-z_$]{21}$")
ALLOWED_OPERATIONS = {"added", "deleted", "property_modified"}
LEDGER_FIELDS = {
    "case_id",
    "global_id",
    "entity_type",
    "operation",
    "field",
    "old_value",
    "new_value",
    "expected_product_result",
}
WINDOWS_PATH = re.compile(r"(?i)(?:[a-z]:[\\/]|\\\\)")
POSIX_PATH = re.compile(r"/(?:home|users|tmp|var|private)/")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _signature(path: Path) -> tuple[int, int, int, int]:
    stat = path.stat()
    return (
        stat.st_size,
        stat.st_mtime_ns,
        stat.st_ctime_ns,
        getattr(stat, "st_ino", 0),
    )


def _inspect_ifc(path: Path, role: str) -> tuple[dict[str, Any], set[str]]:
    path = path.expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != ".ifc":
        raise ValueError(f"{role} must resolve to one .ifc file")
    before = _signature(path)
    digest_before = _sha256(path)
    try:
        model = ifcopenshell.open(path)
    except Exception as error:
        raise ValueError(f"{role} is not a readable IFC") from error
    roots = model.by_type("IfcRoot")
    root_ids = [getattr(entity, "GlobalId", None) for entity in roots]
    valid_ids = [
        value for value in root_ids if isinstance(value, str) and IFC_GUID.fullmatch(value)
    ]
    counts = Counter(valid_ids)
    elements = model.by_type("IfcElement")
    element_ids = {
        entity.GlobalId
        for entity in elements
        if isinstance(getattr(entity, "GlobalId", None), str)
        and IFC_GUID.fullmatch(entity.GlobalId)
    }
    digest_after = _sha256(path)
    after = _signature(path)
    if before != after or digest_before != digest_after:
        raise ValueError(f"{role} changed while being inspected")
    return (
        {
            "role": role,
            "sha256": digest_before,
            "file_size_bytes": before[0],
            "ifc_schema": model.schema,
            "entity_count": sum(1 for _ in model),
            "element_count": len(elements),
            "root_count": len(roots),
            "missing_or_invalid_root_guid_count": len(root_ids) - len(valid_ids),
            "duplicate_root_guid_excess_count": sum(
                count - 1 for count in counts.values() if count > 1
            ),
        },
        element_ids,
    )


def _inspect_ledger(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ValueError("ledger must resolve to one CSV file")
    before = _signature(path)
    digest_before = _sha256(path)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or [])
        if fields != LEDGER_FIELDS:
            raise ValueError("ledger fields do not match the frozen minimal contract")
        rows = list(reader)
    if not rows:
        raise ValueError("ledger contains no change rows")
    case_ids = [row["case_id"] for row in rows]
    global_ids = [row["global_id"] for row in rows]
    operations = [row["operation"] for row in rows]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("ledger contains duplicate case_id values")
    if len(global_ids) != len(set(global_ids)):
        raise ValueError("ledger contains duplicate GlobalId values")
    if any(not IFC_GUID.fullmatch(value) for value in global_ids):
        raise ValueError("ledger contains an invalid GlobalId")
    if any(value not in ALLOWED_OPERATIONS for value in operations):
        raise ValueError("ledger contains an operation outside the R1 scope")
    digest_after = _sha256(path)
    if before != _signature(path) or digest_before != digest_after:
        raise ValueError("ledger changed while being inspected")
    operation_counts = Counter(operations)
    return {
        "role": "change-ledger.csv",
        "sha256": digest_before,
        "row_count": len(rows),
        "operation_counts": {
            operation: operation_counts[operation]
            for operation in sorted(ALLOWED_OPERATIONS)
        },
        "case_id_set_sha256": _canonical_digest(sorted(case_ids)),
        "global_id_set_sha256": _canonical_digest(sorted(global_ids)),
    }


def _privacy_violations(value: Any) -> int:
    if isinstance(value, dict):
        return sum(_privacy_violations(item) for item in value.values())
    if isinstance(value, list):
        return sum(_privacy_violations(item) for item in value)
    if isinstance(value, str):
        return int(bool(WINDOWS_PATH.search(value) or POSIX_PATH.search(value)))
    return 0


def audit_sample_set(
    baseline: Path,
    repeat: Path,
    revised: Path,
    ifc2x3_boundary: Path,
    ledger: Path,
) -> dict[str, Any]:
    """Audit one authorised A/B/C IFC4 set and one IFC2X3 boundary sample.

    Input paths are used only during execution and are never returned.
    """

    inspected: dict[str, dict[str, Any]] = {}
    element_ids: dict[str, set[str]] = {}
    for role, path in (
        ("ifc4_baseline", baseline),
        ("ifc4_repeat", repeat),
        ("ifc4_revised", revised),
        ("ifc2x3_boundary", ifc2x3_boundary),
    ):
        inspected[role], element_ids[role] = _inspect_ifc(path, role)
    ledger_report = _inspect_ledger(ledger)
    denominator = min(
        len(element_ids["ifc4_baseline"]), len(element_ids["ifc4_revised"])
    )
    shared_ratio = (
        len(element_ids["ifc4_baseline"] & element_ids["ifc4_revised"])
        / denominator
        if denominator
        else 0.0
    )
    guid_quality_pass = all(
        report["missing_or_invalid_root_guid_count"] == 0
        and report["duplicate_root_guid_excess_count"] == 0
        for report in inspected.values()
    )
    ifc4_roles_are_ifc4 = all(
        inspected[role]["ifc_schema"] == "IFC4"
        for role in ("ifc4_baseline", "ifc4_repeat", "ifc4_revised")
    )
    baseline_repeat_identical = (
        inspected["ifc4_baseline"]["sha256"]
        == inspected["ifc4_repeat"]["sha256"]
    )
    categories_present = all(
        ledger_report["operation_counts"][operation] > 0
        for operation in sorted(ALLOWED_OPERATIONS)
    )
    report: dict[str, Any] = {
        "protocol_id": PROTOCOL_ID,
        "status": "PASS"
        if (
            guid_quality_pass
            and ifc4_roles_are_ifc4
            and baseline_repeat_identical
            and inspected["ifc2x3_boundary"]["ifc_schema"] == "IFC2X3"
            and categories_present
            and shared_ratio >= 0.5
        )
        else "FAIL",
        "authorization_basis": "user_asserted_local_research_authorization",
        "samples": inspected,
        "ledger": ledger_report,
        "checks": {
            "ifc4_roles_are_exact_ifc4": ifc4_roles_are_ifc4,
            "baseline_repeat_byte_identical": baseline_repeat_identical,
            "baseline_revised_shared_element_guid_ratio": round(shared_ratio, 6),
            "all_root_guids_complete_and_unique": guid_quality_pass,
            "ledger_covers_all_r1_change_categories": categories_present,
            "ifc2x3_boundary_schema_confirmed": inspected["ifc2x3_boundary"][
                "ifc_schema"
            ]
            == "IFC2X3",
        },
        "research_state": {
            "ifc4_external_replication": "READY",
            "ifc2x3_cross_schema_pair": "NOT_AVAILABLE_SINGLE_FILE_ONLY",
            "ifc2x3_product_support_claim": "NOT_PERMITTED",
        },
        "privacy_violation_count": 0,
        "model_calls_made": 0,
    }
    report["privacy_violation_count"] = _privacy_violations(report)
    if report["privacy_violation_count"]:
        report["status"] = "FAIL"
    return report


def write_json(path: Path, value: dict[str, Any]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--repeat", required=True, type=Path)
    parser.add_argument("--revised", required=True, type=Path)
    parser.add_argument("--ifc2x3-boundary", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_sample_set(
        args.baseline,
        args.repeat,
        args.revised,
        args.ifc2x3_boundary,
        args.ledger,
    )
    if args.output:
        write_json(args.output, report)
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
