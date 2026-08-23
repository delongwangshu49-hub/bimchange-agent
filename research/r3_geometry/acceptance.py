"""Run the complete offline R3-A placement-translation acceptance gate."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import ifcopenshell

from .protocol import (
    EXPECTED_DETECTOR,
    MANIFEST_SCHEMA_VERSION,
    PRIMARY_DELTA_M,
    PROTOCOL_ID,
    ROLE_NAMES,
    TARGET_GLOBAL_ID,
    VECTOR_DELTA_M,
    build_bundle,
    digest_value,
    generate_revision,
    normalized_ifcdiff_semantics,
    reconstruct_translation_record,
    run_geometry_diff,
    sha256_file,
    strict_load_json,
    verify_bundle,
    write_json,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = REPOSITORY_ROOT / "data" / "raw" / "Building-Structural.ifc"


def _evaluate_variant(
    source: Path,
    root: Path,
    case_id: str,
    *,
    variant: str,
    delta_m: tuple[float, float, float] = PRIMARY_DELTA_M,
) -> dict[str, Any]:
    revised = root / f"{case_id}.ifc"
    ledger = generate_revision(
        source,
        revised,
        variant=variant,
        delta_m=delta_m,
    )
    source_model = ifcopenshell.open(source)
    revised_model = ifcopenshell.open(revised)
    raw = run_geometry_diff(source_model, revised_model)
    flags = raw["changed"].get(TARGET_GLOBAL_ID)
    detected = isinstance(flags, dict) and flags.get("geometry_changed") is True
    supported = False
    classification_code = "supported"
    try:
        reconstruct_translation_record(source_model, revised_model, raw, ledger)
        supported = True
    except Exception as error:
        classification_code = getattr(error, "code", type(error).__name__)
    return {
        "case_id": case_id,
        "variant": variant,
        "detected_geometry_flag": detected,
        "raw_changed_global_ids": sorted(raw["changed"]),
        "classified_supported": supported,
        "classification_code": classification_code,
        "delta_m": list(delta_m) if variant == "translation" else None,
    }


def evaluate_controls(source: Path, root: Path) -> list[dict[str, Any]]:
    source_a = ifcopenshell.open(source)
    source_b = ifcopenshell.open(source)
    exact_raw = run_geometry_diff(source_a, source_b)
    controls = [
        {
            "case_id": "C0-exact",
            "variant": "exact_same_input",
            "detected_geometry_flag": bool(exact_raw["changed"]),
            "raw_changed_global_ids": sorted(exact_raw["changed"]),
            "classified_supported": False,
            "classification_code": "zero_change_control",
            "delta_m": None,
        }
    ]
    controls.extend(
        [
            _evaluate_variant(source, root, "C1-noop-rewrite", variant="noop"),
            _evaluate_variant(source, root, "P1-translation-x", variant="translation", delta_m=PRIMARY_DELTA_M),
            _evaluate_variant(source, root, "P2-translation-vector", variant="translation", delta_m=VECTOR_DELTA_M),
            _evaluate_variant(source, root, "N1-sub-detector-noise", variant="translation", delta_m=(5e-6, 0.0, 0.0)),
            _evaluate_variant(source, root, "N2-boundary-1e-5", variant="translation", delta_m=(1e-5, 0.0, 0.0)),
            _evaluate_variant(source, root, "N2-boundary-2e-5", variant="translation", delta_m=(2e-5, 0.0, 0.0)),
            _evaluate_variant(source, root, "N3-rotation-only", variant="rotation"),
            _evaluate_variant(source, root, "N4-local-shape-change", variant="local_shape"),
            _evaluate_variant(source, root, "N5-missing-body", variant="missing_body"),
        ]
    )
    return controls


def _bundle_values(directory: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        strict_load_json(directory / ROLE_NAMES["ledger"]),
        strict_load_json(directory / ROLE_NAMES["raw"]),
        strict_load_json(directory / ROLE_NAMES["records"]),
        strict_load_json(directory / ROLE_NAMES["manifest"]),
    )


def _append_source_bytes(directory: Path) -> None:
    with (directory / ROLE_NAMES["source"]).open("ab") as stream:
        stream.write(b"\n")


def _append_revised_bytes(directory: Path) -> None:
    with (directory / ROLE_NAMES["revised"]).open("ab") as stream:
        stream.write(b"\n")


def _raw_flag_false(directory: Path) -> None:
    _, raw, _, _ = _bundle_values(directory)
    raw["changed"][TARGET_GLOBAL_ID]["geometry_changed"] = False
    write_json(directory / ROLE_NAMES["raw"], raw)


def _raw_global_id(directory: Path) -> None:
    _, raw, _, _ = _bundle_values(directory)
    raw["changed"]["0AAAAAAAAAAAAAAAAAAAAA"] = raw["changed"].pop(TARGET_GLOBAL_ID)
    write_json(directory / ROLE_NAMES["raw"], raw)


def _duplicate_json_key(directory: Path) -> None:
    path = directory / ROLE_NAMES["raw"]
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace('"changed":', '"changed": {}, "changed":', 1), encoding="utf-8")


def _duplicate_record(directory: Path) -> None:
    _, _, records, _ = _bundle_values(directory)
    records["changes"].append(records["changes"][0])
    write_json(directory / ROLE_NAMES["records"], records)


def _omit_record(directory: Path) -> None:
    _, _, records, _ = _bundle_values(directory)
    records["changes"] = []
    write_json(directory / ROLE_NAMES["records"], records)


def _extra_record(directory: Path) -> None:
    _, _, records, _ = _bundle_values(directory)
    extra = json.loads(json.dumps(records["changes"][0]))
    extra["change_id"] = "chg-" + "a" * 16
    records["changes"].append(extra)
    write_json(directory / ROLE_NAMES["records"], records)


def _entity_type(directory: Path) -> None:
    _, _, records, _ = _bundle_values(directory)
    records["changes"][0]["entity_type"] = "IfcWall"
    write_json(directory / ROLE_NAMES["records"], records)


def _origin(directory: Path) -> None:
    _, _, records, _ = _bundle_values(directory)
    records["changes"][0]["geometry_change"]["old_origin"][0] += 1.0
    write_json(directory / ROLE_NAMES["records"], records)


def _delta_and_unit(directory: Path) -> None:
    _, _, records, _ = _bundle_values(directory)
    geometry = records["changes"][0]["geometry_change"]
    geometry["delta"] = [-value for value in geometry["delta"]]
    geometry["length_unit"] = "mm"
    write_json(directory / ROLE_NAMES["records"], records)


def _distance(directory: Path) -> None:
    _, _, records, _ = _bundle_values(directory)
    records["changes"][0]["geometry_change"]["distance"] += 0.5
    write_json(directory / ROLE_NAMES["records"], records)


def _shape_evidence(directory: Path) -> None:
    _, _, records, _ = _bundle_values(directory)
    evidence = records["changes"][0]["evidence"]["reconstruction"]
    evidence["revised_local_shape_sha256"] = "0" * 64
    records["changes"][0]["geometry_change"]["local_shape_unchanged"] = False
    write_json(directory / ROLE_NAMES["records"], records)


def _configuration(directory: Path) -> None:
    _, _, records, _ = _bundle_values(directory)
    records["detector"]["version"] = "0.8.4"
    records["tolerances"]["translation_support_threshold_m"] = 0.5
    write_json(directory / ROLE_NAMES["records"], records)


def _coordinated_forgery(directory: Path) -> None:
    _, _, records, manifest = _bundle_values(directory)
    record = records["changes"][0]
    record["geometry_change"]["delta"][0] += 0.5
    record["geometry_change"]["new_origin"][0] += 0.5
    record["geometry_change"]["distance"] += 0.5
    record_body = {key: value for key, value in record.items() if key != "change_id"}
    record["change_id"] = f"chg-{digest_value(record_body)[:16]}"
    records_path = directory / ROLE_NAMES["records"]
    write_json(records_path, records)
    binding = manifest["artifacts"]["geometry_records"]
    binding["sha256"] = sha256_file(records_path)
    binding["canonical_json_sha256"] = digest_value(records)
    entry = manifest["entries"][0]
    entry["change_id"] = record["change_id"]
    entry["change_record_sha256"] = digest_value(record)
    entry["reconstructed_fact_sha256"] = digest_value(record["geometry_change"])
    entry_body = {key: value for key, value in entry.items() if key != "trace_id"}
    entry["trace_id"] = f"trace-{digest_value(entry_body)[:24]}"
    write_json(directory / ROLE_NAMES["manifest"], manifest)


def _privacy_path(directory: Path) -> None:
    _, _, _, manifest = _bundle_values(directory)
    manifest["artifacts"]["source"]["role_name"] = "C:\\private\\project.ifc"
    write_json(directory / ROLE_NAMES["manifest"], manifest)


TAMPER_CASES: tuple[tuple[str, Callable[[Path], None]], ...] = (
    ("source_ifc_bytes", _append_source_bytes),
    ("revised_ifc_bytes", _append_revised_bytes),
    ("raw_geometry_flag", _raw_flag_false),
    ("raw_global_id", _raw_global_id),
    ("duplicate_json_key", _duplicate_json_key),
    ("duplicate_record", _duplicate_record),
    ("record_omission", _omit_record),
    ("extra_record", _extra_record),
    ("entity_type", _entity_type),
    ("old_origin", _origin),
    ("delta_axis_sign_unit", _delta_and_unit),
    ("distance", _distance),
    ("local_shape_evidence", _shape_evidence),
    ("detector_and_tolerance_configuration", _configuration),
    ("coordinated_record_manifest_forgery", _coordinated_forgery),
    ("privacy_absolute_path", _privacy_path),
)


def _controls_pass(controls: list[dict[str, Any]]) -> bool:
    by_id = {item["case_id"]: item for item in controls}
    return (
        not by_id["C0-exact"]["detected_geometry_flag"]
        and not by_id["C1-noop-rewrite"]["detected_geometry_flag"]
        and by_id["P1-translation-x"]["detected_geometry_flag"]
        and by_id["P1-translation-x"]["classified_supported"]
        and by_id["P2-translation-vector"]["detected_geometry_flag"]
        and by_id["P2-translation-vector"]["classified_supported"]
        and not by_id["N1-sub-detector-noise"]["classified_supported"]
        and not by_id["N2-boundary-1e-5"]["classified_supported"]
        and not by_id["N2-boundary-2e-5"]["classified_supported"]
        and by_id["N3-rotation-only"]["detected_geometry_flag"]
        and not by_id["N3-rotation-only"]["classified_supported"]
        and by_id["N4-local-shape-change"]["detected_geometry_flag"]
        and not by_id["N4-local-shape-change"]["classified_supported"]
        and not by_id["N5-missing-body"]["classified_supported"]
    )


def run_acceptance(source: Path = DEFAULT_SOURCE) -> dict[str, Any]:
    source = source.resolve()
    with tempfile.TemporaryDirectory(prefix="bimchange-r3a-acceptance-") as directory:
        root = Path(directory)
        clean_a = root / "clean-a"
        clean_b = root / "clean-b"
        report_a = build_bundle(source, clean_a)
        report_b = build_bundle(source, clean_b)
        compared_roles = tuple(ROLE_NAMES.values())
        clean_role_matches = {
            role: (clean_a / role).read_bytes() == (clean_b / role).read_bytes()
            for role in compared_roles
        }
        clean_rebuild_match = all(clean_role_matches.values())
        controls = evaluate_controls(source, root / "controls")
        tamper_results: list[dict[str, Any]] = []
        for index, (case_id, mutator) in enumerate(TAMPER_CASES, start=1):
            case_dir = root / f"tamper-{index:02d}"
            shutil.copytree(clean_a, case_dir)
            mutator(case_dir)
            result = verify_bundle(case_dir)
            tamper_results.append(
                {
                    "case_id": case_id,
                    "status": result["status"],
                    "failure_codes": [item["code"] for item in result["failures"]],
                }
            )
        rejected = sum(item["status"] == "FAIL" for item in tamper_results)
        false_acceptance = len(tamper_results) - rejected
        controls_passed = _controls_pass(controls)
        status = (
            "PASS"
            if report_a["status"] == report_b["status"] == "PASS"
            and clean_rebuild_match
            and controls_passed
            and rejected == len(TAMPER_CASES)
            and false_acceptance == 0
            and report_a["privacy_violation_count"] == 0
            else "FAIL"
        )
        return {
            "status": status,
            "protocol_id": PROTOCOL_ID,
            "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            "clean_runs": 2,
            "clean_runs_passed": sum(report["status"] == "PASS" for report in (report_a, report_b)),
            "clean_rebuild_match": clean_rebuild_match,
            "clean_role_matches": clean_role_matches,
            "manifest_sha256": sha256_file(clean_a / ROLE_NAMES["manifest"]),
            "revised_ifc_sha256": sha256_file(clean_a / ROLE_NAMES["revised"]),
            "supported_change_records": report_a["supported_change_records"],
            "trace_resolution_rate": report_a["trace_resolution_rate"],
            "controls_passed": controls_passed,
            "control_cases": len(controls),
            "controls": controls,
            "tamper_cases": len(TAMPER_CASES),
            "tamper_rejected": rejected,
            "tamper_rejection_rate": rejected / len(TAMPER_CASES),
            "false_acceptance_count": false_acceptance,
            "tamper_results": tamper_results,
            "privacy_violation_count": report_a["privacy_violation_count"],
            "model_calls_made": 0,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_acceptance(args.source)
    if args.output is not None:
        write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
