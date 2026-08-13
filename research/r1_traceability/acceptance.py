"""Offline acceptance harness for R1 clean rebuilds and controlled tampering."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable

from bimchange_agent.product_core import (
    CHANGE_RECORD_FILE_NAME,
    RAW_DIFF_FILE_NAME,
    diff_ifc_pair,
)

from .traceability import (
    MANIFEST_FILE_NAME,
    _trace_id,
    digest_value,
    generate_trace_manifest,
    sha256_file,
    strict_load_json,
    verify_trace_manifest,
    write_json,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = REPOSITORY_ROOT / "data" / "raw" / "Building-Structural.ifc"
DEFAULT_REVISED = (
    REPOSITORY_ROOT
    / "data"
    / "generated"
    / "Building-Structural-gate2-v2.ifc"
)


def _build_clean_bundle(source: Path, revised: Path, output: Path) -> dict[str, Any]:
    diff_ifc_pair(source, revised, output)
    records = output / CHANGE_RECORD_FILE_NAME
    raw = output / RAW_DIFF_FILE_NAME
    manifest_path = output / MANIFEST_FILE_NAME
    manifest = generate_trace_manifest(source, revised, records, raw)
    write_json(manifest_path, manifest)
    report = verify_trace_manifest(
        manifest_path, source, revised, records, raw
    )
    if report["status"] != "PASS":
        raise RuntimeError(f"Clean R1 bundle failed verification: {report}")
    return report


def _paths(directory: Path) -> tuple[Path, Path, Path]:
    return (
        directory / MANIFEST_FILE_NAME,
        directory / CHANGE_RECORD_FILE_NAME,
        directory / RAW_DIFF_FILE_NAME,
    )


def _load_bundle(directory: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest_path, records_path, raw_path = _paths(directory)
    return (
        strict_load_json(manifest_path),
        strict_load_json(records_path),
        strict_load_json(raw_path),
    )


def _save_manifest(directory: Path, manifest: dict[str, Any]) -> None:
    write_json(directory / MANIFEST_FILE_NAME, manifest)


def _save_records(
    directory: Path, manifest: dict[str, Any], records: dict[str, Any]
) -> None:
    path = directory / CHANGE_RECORD_FILE_NAME
    write_json(path, records)
    manifest["artifacts"]["change_records"]["sha256"] = sha256_file(path)
    manifest["artifacts"]["change_records"]["canonical_json_sha256"] = digest_value(
        records
    )


def _save_raw(
    directory: Path, manifest: dict[str, Any], raw: dict[str, Any]
) -> None:
    path = directory / RAW_DIFF_FILE_NAME
    write_json(path, raw)
    manifest["artifacts"]["raw_result"]["sha256"] = sha256_file(path)
    manifest["artifacts"]["raw_result"]["canonical_json_sha256"] = digest_value(raw)


def _find_entry(manifest: dict[str, Any], change_type: str) -> dict[str, Any]:
    return next(
        entry for entry in manifest["entries"] if entry["change_type"] == change_type
    )


def _find_record(records: dict[str, Any], change_type: str) -> dict[str, Any]:
    return next(
        record for record in records["changes"] if record["change_type"] == change_type
    )


def _tamper_input_hash(directory: Path) -> None:
    manifest, _, _ = _load_bundle(directory)
    manifest["artifacts"]["source"]["sha256"] = "0" * 64
    _save_manifest(directory, manifest)


def _tamper_global_id(directory: Path) -> None:
    manifest, _, _ = _load_bundle(directory)
    entry = _find_entry(manifest, "added")
    entry["global_id"] = "0" + "A" * 21
    entry["raw_evidence"]["locator"]["global_id"] = entry["global_id"]
    _save_manifest(directory, manifest)


def _tamper_locator(directory: Path) -> None:
    manifest, _, _ = _load_bundle(directory)
    entry = _find_entry(manifest, "added")
    entry["raw_evidence"]["locator"]["section"] = "deleted"
    _save_manifest(directory, manifest)


def _tamper_raw_value_with_updated_hashes(directory: Path) -> None:
    manifest, _, raw = _load_bundle(directory)
    entry = _find_entry(manifest, "property_modified")
    locator = entry["raw_evidence"]["locator"]
    raw["changed"][locator["global_id"]]["properties_changed"]["values_changed"][
        locator["property_path"]
    ]["new_value"] = "tampered"
    _save_raw(directory, manifest, raw)
    _save_manifest(directory, manifest)


def _tamper_detector(directory: Path) -> None:
    manifest, _, _ = _load_bundle(directory)
    manifest["detector"]["configuration"]["is_shallow"] = True
    _save_manifest(directory, manifest)


def _tamper_normalized_fact_with_updated_digests(directory: Path) -> None:
    manifest, records, _ = _load_bundle(directory)
    record = _find_record(records, "property_modified")
    record["new_value"] = "tampered"
    _save_records(directory, manifest, records)
    entry = next(
        item for item in manifest["entries"] if item["change_id"] == record["change_id"]
    )
    entry["change_record_sha256"] = digest_value(record)
    entry_without_id = {key: value for key, value in entry.items() if key != "trace_id"}
    entry["trace_id"] = _trace_id(entry_without_id)
    _save_manifest(directory, manifest)


def _tamper_change_record_stale_digest(directory: Path) -> None:
    _, records, _ = _load_bundle(directory)
    _find_record(records, "added")["new_value"]["name"] = "tampered"
    write_json(directory / CHANGE_RECORD_FILE_NAME, records)


def _tamper_privacy(directory: Path) -> None:
    manifest, _, _ = _load_bundle(directory)
    drive_prefix = "C" + ":"
    manifest["artifacts"]["source"]["role_name"] = (
        drive_prefix + "\\private\\project.ifc"
    )
    _save_manifest(directory, manifest)


def _tamper_uniqueness_with_updated_hashes(directory: Path) -> None:
    manifest, _, raw = _load_bundle(directory)
    raw["added"].append(raw["added"][0])
    _save_raw(directory, manifest, raw)
    _save_manifest(directory, manifest)


def _tamper_unsupported_scope(directory: Path) -> None:
    manifest, _, _ = _load_bundle(directory)
    entry = _find_entry(manifest, "added")
    entry["change_type"] = "geometry_modified"
    _save_manifest(directory, manifest)


def _tamper_entry_omission(directory: Path) -> None:
    manifest, _, _ = _load_bundle(directory)
    manifest["entries"].pop()
    manifest["summary"]["resolved_unique"] -= 1
    manifest["summary"]["trace_resolution_rate"] = 2 / 3
    _save_manifest(directory, manifest)


def _tamper_summary(directory: Path) -> None:
    manifest, _, _ = _load_bundle(directory)
    manifest["summary"]["resolved_unique"] = 2
    manifest["summary"]["trace_resolution_rate"] = 2 / 3
    _save_manifest(directory, manifest)


def _tamper_duplicate_json_key(directory: Path) -> None:
    raw_path = directory / RAW_DIFF_FILE_NAME
    text = raw_path.read_text(encoding="utf-8")
    raw_path.write_text(
        text.replace('"added":', '"added_duplicate_guard": [], "added":', 1).replace(
            '"added_duplicate_guard": []', '"added": []', 1
        ),
        encoding="utf-8",
    )


TAMPER_CASES: tuple[tuple[str, Callable[[Path], None]], ...] = (
    ("input_hash", _tamper_input_hash),
    ("global_id", _tamper_global_id),
    ("evidence_locator", _tamper_locator),
    ("raw_value_coordinated_hash", _tamper_raw_value_with_updated_hashes),
    ("detector_configuration", _tamper_detector),
    ("normalized_fact_coordinated_digest", _tamper_normalized_fact_with_updated_digests),
    ("change_record_stale_digest", _tamper_change_record_stale_digest),
    ("privacy_absolute_path", _tamper_privacy),
    ("raw_guid_uniqueness", _tamper_uniqueness_with_updated_hashes),
    ("unsupported_scope", _tamper_unsupported_scope),
    ("entry_omission", _tamper_entry_omission),
    ("summary_forgery", _tamper_summary),
    ("duplicate_json_key", _tamper_duplicate_json_key),
)


def run_acceptance(source: Path, revised: Path) -> dict[str, Any]:
    source = source.resolve()
    revised = revised.resolve()
    with tempfile.TemporaryDirectory(prefix="bimchange-r1-acceptance-") as directory:
        root = Path(directory)
        clean_a = root / "clean-a"
        clean_b = root / "clean-b"
        clean_a.mkdir()
        clean_b.mkdir()
        report_a = _build_clean_bundle(source, revised, clean_a)
        report_b = _build_clean_bundle(source, revised, clean_b)
        manifest_a = clean_a / MANIFEST_FILE_NAME
        manifest_b = clean_b / MANIFEST_FILE_NAME
        clean_rebuild_match = manifest_a.read_bytes() == manifest_b.read_bytes()
        tamper_results: list[dict[str, Any]] = []
        for index, (case_id, mutator) in enumerate(TAMPER_CASES, start=1):
            case_dir = root / f"tamper-{index:02d}"
            shutil.copytree(clean_a, case_dir)
            mutator(case_dir)
            manifest, records, raw = _paths(case_dir)
            result = verify_trace_manifest(
                manifest, source, revised, records, raw
            )
            tamper_results.append(
                {
                    "case_id": case_id,
                    "status": result["status"],
                    "failure_codes": [
                        item["code"] for item in result.get("failures", [])
                    ],
                }
            )
        rejected = sum(item["status"] == "FAIL" for item in tamper_results)
        false_acceptance_count = len(tamper_results) - rejected
        status = (
            "PASS"
            if report_a["status"] == report_b["status"] == "PASS"
            and report_a["trace_resolution_rate"] == 1.0
            and report_b["trace_resolution_rate"] == 1.0
            and clean_rebuild_match
            and rejected == len(tamper_results)
            and report_a["privacy_violation_count"] == 0
            else "FAIL"
        )
        return {
            "status": status,
            "protocol_id": report_a["protocol_id"],
            "clean_runs": 2,
            "clean_runs_passed": 2
            if report_a["status"] == report_b["status"] == "PASS"
            else 0,
            "supported_change_records": report_a["supported_change_records"],
            "supported_change_types": report_a["supported_change_types"],
            "trace_resolution_rate": report_a["trace_resolution_rate"],
            "clean_rebuild_match": clean_rebuild_match,
            "manifest_sha256": sha256_file(manifest_a),
            "tamper_cases": len(tamper_results),
            "tamper_rejected": rejected,
            "tamper_rejection_rate": rejected / len(tamper_results),
            "false_acceptance_count": false_acceptance_count,
            "privacy_violation_count": report_a["privacy_violation_count"],
            "tamper_results": tamper_results,
            "model_calls_made": 0,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--revised", type=Path, default=DEFAULT_REVISED)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_acceptance(args.source, args.revised)
    if args.output is not None:
        write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
