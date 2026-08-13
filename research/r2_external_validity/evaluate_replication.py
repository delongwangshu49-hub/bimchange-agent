"""Evaluate an IFC4 A/B/C replication against its ledger and R1 acceptance."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from bimchange_agent.product_core import validate_product_artifact

from .preflight import (
    ALLOWED_OPERATIONS,
    LEDGER_FIELDS,
    PROTOCOL_ID,
    _canonical_digest,
    _privacy_violations,
    write_json,
)


DERIVED_FIELDS = (
    "change_type",
    "entity_type",
    "global_id",
    "location",
    "field",
    "old_value",
    "new_value",
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path.name}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_ledger(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or []) != LEDGER_FIELDS:
            raise ValueError("ledger fields do not match the frozen minimal contract")
        return list(reader)


def _semantic_digest(artifact: dict[str, Any]) -> str:
    facts = [
        {field: record[field] for field in DERIVED_FIELDS}
        for record in artifact["changes"]
    ]
    return _canonical_digest(facts)


def _parse_ledger_value(value: str) -> Any:
    if value == "":
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _field_name(record: dict[str, Any]) -> str:
    field = record["field"]
    if field is None:
        return ""
    return f"{field['property_set']}.{field['name']}"


def _ledger_row_matches(row: dict[str, str], record: dict[str, Any]) -> bool:
    if (
        row["global_id"] != record["global_id"]
        or row["entity_type"] != record["entity_type"]
        or row["operation"] != record["change_type"]
        or row["expected_product_result"] != record["change_type"]
        or row["field"] != _field_name(record)
    ):
        return False
    if record["change_type"] == "property_modified":
        return (
            _parse_ledger_value(row["old_value"]) == record["old_value"]
            and _parse_ledger_value(row["new_value"]) == record["new_value"]
        )
    if record["change_type"] == "added":
        expected = _parse_ledger_value(row["new_value"])
        return (
            row["old_value"] == ""
            and isinstance(expected, dict)
            and all(record["new_value"].get(key) == value for key, value in expected.items())
        )
    return row["new_value"] == "" and record["old_value"] is not None


def evaluate_replication(
    ab: dict[str, Any],
    bc: dict[str, Any],
    ac: dict[str, Any],
    ledger_rows: list[dict[str, str]],
    acceptance: dict[str, Any],
    bc_manifest: dict[str, Any],
    bc_manifest_file_sha256: str,
) -> dict[str, Any]:
    for artifact in (ab, bc, ac):
        validate_product_artifact(artifact)
    expected_counts = Counter(row["operation"] for row in ledger_rows)
    expected_summary = {
        "total_supported": len(ledger_rows),
        "added": expected_counts["added"],
        "deleted": expected_counts["deleted"],
        "property_modified": expected_counts["property_modified"],
        "unsupported": 0,
    }
    bc_by_guid = {record["global_id"]: record for record in bc["changes"]}
    ledger_matches = [
        row["global_id"] in bc_by_guid
        and _ledger_row_matches(row, bc_by_guid[row["global_id"]])
        for row in ledger_rows
    ]
    semantic_bc = _semantic_digest(bc)
    semantic_ac = _semantic_digest(ac)
    case_ids = [row["case_id"] for row in ledger_rows]
    ledger_ids = [row["global_id"] for row in ledger_rows]
    operations = {row["operation"] for row in ledger_rows}
    checks = {
        "ab_zero_supported_and_unsupported": ab["summary"]
        == {
            "total_supported": 0,
            "added": 0,
            "deleted": 0,
            "property_modified": 0,
            "unsupported": 0,
        },
        "bc_summary_matches_ledger": bc["summary"] == expected_summary,
        "ac_summary_matches_ledger": ac["summary"] == expected_summary,
        "bc_ac_semantic_facts_identical": semantic_bc == semantic_ac,
        "ledger_rows_match_bc_records": all(ledger_matches)
        and len(ledger_matches) == len(bc["changes"]),
        "ledger_identifiers_unique_and_scope_exact": len(case_ids) == len(set(case_ids))
        and len(ledger_ids) == len(set(ledger_ids))
        and operations == ALLOWED_OPERATIONS,
        "r1_acceptance_bound_to_bc_manifest": acceptance.get("manifest_sha256")
        == bc_manifest_file_sha256
        and bc_manifest.get("artifacts", {}).get("source", {}).get("sha256")
        == bc["source"]["sha256"]
        and bc_manifest.get("artifacts", {}).get("revised", {}).get("sha256")
        == bc["revised"]["sha256"]
        and bc_manifest.get("artifacts", {})
        .get("change_records", {})
        .get("canonical_json_sha256")
        == _canonical_digest(bc),
        "r1_trace_resolution_complete": acceptance.get("trace_resolution_rate") == 1.0,
        "r1_clean_runs_reproducible": acceptance.get("clean_runs_passed") == 2
        and acceptance.get("clean_rebuild_match") is True,
        "r1_tamper_rejection_complete": acceptance.get("tamper_cases") == 13
        and acceptance.get("tamper_rejected") == 13
        and acceptance.get("false_acceptance_count") == 0,
        "privacy_and_model_boundary": acceptance.get("privacy_violation_count") == 0
        and acceptance.get("model_calls_made") == 0,
    }
    report: dict[str, Any] = {
        "protocol_id": PROTOCOL_ID,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "ledger_row_count": len(ledger_rows),
        "ledger_rows_matched": sum(ledger_matches),
        "supported_change_types": sorted(
            {row["operation"] for row in ledger_rows} & ALLOWED_OPERATIONS
        ),
        "bc_semantic_facts_sha256": semantic_bc,
        "ac_semantic_facts_sha256": semantic_ac,
        "r1_manifest_sha256": acceptance.get("manifest_sha256"),
        "privacy_violation_count": 0,
        "model_calls_made": 0,
    }
    report["privacy_violation_count"] = _privacy_violations(report)
    if report["privacy_violation_count"]:
        report["status"] = "FAIL"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ab-records", required=True, type=Path)
    parser.add_argument("--bc-records", required=True, type=Path)
    parser.add_argument("--ac-records", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--r1-acceptance", required=True, type=Path)
    parser.add_argument("--bc-manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    bc_manifest = _load_json(args.bc_manifest)
    report = evaluate_replication(
        _load_json(args.ab_records),
        _load_json(args.bc_records),
        _load_json(args.ac_records),
        _load_ledger(args.ledger),
        _load_json(args.r1_acceptance),
        bc_manifest,
        _sha256(args.bc_manifest),
    )
    if args.output:
        write_json(args.output, report)
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
