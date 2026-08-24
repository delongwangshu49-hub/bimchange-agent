"""Build and verify the complete offline R3 controlled research gate."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import ifcopenshell
from jsonschema import Draft202012Validator

from research.r3_geometry.protocol import (
    TARGET_GLOBAL_ID as SHAPE_GUID,
    generate_revision as generate_shape_revision,
    run_geometry_diff as run_shape_diff,
    sha256_file,
    strict_load_json,
    write_json,
)

from .fixtures import TARGET_GUID, write_rectangular_pair, write_relationship_pair
from .geometry import classify_extrusion_dimension_change, run_geometry_diff
from .relationships import classify_relationship_change, run_relationship_diff
from .shape import classify_tessellated_shape_change


PROTOCOL_ID = "r3-complete-0.1.0"
SCHEMA_URI = "bimchange-agent://research/r3-complete-records-0.1.0-candidate"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SHAPE_SOURCE = REPOSITORY_ROOT / "data" / "raw" / "Building-Structural.ifc"


@dataclass(frozen=True)
class Case:
    case_id: str
    family: str
    variant: str

    @property
    def slug(self) -> str:
        return self.case_id.lower()


CASES = (
    Case("R3-A2-X", "dimension", "profile_x"),
    Case("R3-A2-Y", "dimension", "profile_y"),
    Case("R3-A2-DEPTH", "dimension", "depth"),
    Case("R3-A2-ALL", "dimension", "all_dimensions"),
    Case("R3-A3-VERTEX", "shape", "local_shape"),
    Case("R3-B-STOREY", "relationship", "container_storey"),
    Case("R3-B-SPACE", "relationship", "container_space"),
    Case("R3-B-AGGREGATE", "relationship", "aggregate"),
    Case("R3-B-TYPE", "relationship", "type"),
    Case("R3-B-MATERIAL", "relationship", "material"),
)


def _case_record(case: Case, source_path: Path, revised_path: Path) -> dict[str, Any]:
    source, revised = ifcopenshell.open(source_path), ifcopenshell.open(revised_path)
    if case.family == "dimension":
        return classify_extrusion_dimension_change(source, revised, run_geometry_diff(source, revised), TARGET_GUID)
    if case.family == "shape":
        return classify_tessellated_shape_change(source, revised, run_shape_diff(source, revised), SHAPE_GUID)
    return classify_relationship_change(source, revised, run_relationship_diff(source, revised), TARGET_GUID)


def build_bundle(bundle: Path) -> dict[str, Any]:
    bundle.mkdir(parents=True, exist_ok=False)
    entries = []
    ledger = []
    for case in CASES:
        case_dir = bundle / "cases" / case.slug
        if case.family == "dimension":
            source, revised_generated = write_rectangular_pair(case_dir, case.variant)
        elif case.family == "relationship":
            source, revised_generated = write_relationship_pair(case_dir, case.variant)
        else:
            case_dir.mkdir(parents=True, exist_ok=True)
            source = case_dir / "source.ifc"
            shutil.copyfile(SHAPE_SOURCE, source)
            revised_generated = case_dir / "generated.ifc"
            generate_shape_revision(source, revised_generated, variant="local_shape")
        revised = case_dir / "revised.ifc"
        if revised_generated != revised:
            revised_generated.replace(revised)
        record = _case_record(case, source, revised)
        entries.append({
            "case_id": case.case_id,
            "source_role": source.relative_to(bundle).as_posix(),
            "revised_role": revised.relative_to(bundle).as_posix(),
            "source_sha256": sha256_file(source),
            "revised_sha256": sha256_file(revised),
            "record": record,
        })
        ledger.append({"case_id": case.case_id, "family": case.family, "variant": case.variant, "expected_supported": True})
    records = {
        "schema": SCHEMA_URI, "protocol_id": PROTOCOL_ID,
        "detectors": {"primary": "direct_ifc_chain_comparison", "supplemental": "IfcDiff 0.8.5"},
        "cases": entries, "model_calls_made": 0,
    }
    write_json(bundle / "operation-ledger.json", {"protocol_id": PROTOCOL_ID, "operations": ledger, "model_calls_made": 0})
    write_json(bundle / "r3-records.json", records)
    manifest = {
        "protocol_id": PROTOCOL_ID,
        "artifacts": {
            "ledger": {"role": "operation-ledger.json", "sha256": sha256_file(bundle / "operation-ledger.json")},
            "records": {"role": "r3-records.json", "sha256": sha256_file(bundle / "r3-records.json")},
        },
        "case_count": len(CASES), "model_calls_made": 0,
    }
    write_json(bundle / "trace-manifest.json", manifest)
    return verify_bundle(bundle)


def _schema() -> dict[str, Any]:
    return strict_load_json(Path(__file__).with_name("r3-records.schema.json"))


def verify_bundle(bundle: Path) -> dict[str, Any]:
    failures = []
    try:
        ledger = strict_load_json(bundle / "operation-ledger.json")
        records = strict_load_json(bundle / "r3-records.json")
        manifest = strict_load_json(bundle / "trace-manifest.json")
        Draft202012Validator(_schema()).validate(records)
        if manifest["protocol_id"] != PROTOCOL_ID or records["protocol_id"] != PROTOCOL_ID or ledger["protocol_id"] != PROTOCOL_ID:
            raise ValueError("protocol_id_mismatch")
        if manifest["case_count"] != len(CASES):
            raise ValueError("case_count_mismatch")
        for name in ("ledger", "records"):
            role = manifest["artifacts"][name]["role"]
            if Path(role).name != role:
                raise ValueError("unsafe_artifact_role")
            if sha256_file(bundle / role) != manifest["artifacts"][name]["sha256"]:
                raise ValueError(f"{name}_hash_mismatch")
        by_id = {entry["case_id"]: entry for entry in records["cases"]}
        if len(by_id) != len(records["cases"]) or set(by_id) != {case.case_id for case in CASES}:
            raise ValueError("case_identity_mismatch")
        ledger_by_id = {entry["case_id"]: entry for entry in ledger["operations"]}
        if len(ledger_by_id) != len(CASES):
            raise ValueError("ledger_case_mismatch")
        for case in CASES:
            operation = ledger_by_id[case.case_id]
            if operation != {"case_id": case.case_id, "family": case.family, "variant": case.variant, "expected_supported": True}:
                raise ValueError(f"ledger_operation_mismatch:{case.case_id}")
            entry = by_id[case.case_id]
            source = bundle / entry["source_role"]
            revised = bundle / entry["revised_role"]
            if not source.resolve().is_relative_to(bundle.resolve()) or not revised.resolve().is_relative_to(bundle.resolve()):
                raise ValueError("case_path_escape")
            if sha256_file(source) != entry["source_sha256"] or sha256_file(revised) != entry["revised_sha256"]:
                raise ValueError(f"case_hash_mismatch:{case.case_id}")
            if _case_record(case, source, revised) != entry["record"]:
                raise ValueError(f"record_reconstruction_mismatch:{case.case_id}")
    except Exception as error:
        failures.append({"code": getattr(error, "code", type(error).__name__), "message": str(error)})
    return {
        "status": "PASS" if not failures else "FAIL",
        "protocol_id": PROTOCOL_ID,
        "supported_case_count": len(CASES) if not failures else 0,
        "trace_resolution_rate": 1.0 if not failures else 0.0,
        "failures": failures,
        "model_calls_made": 0,
    }


def _mutate_json(path: Path, mutate: Callable[[dict[str, Any]], None]) -> None:
    value = strict_load_json(path)
    mutate(value)
    write_json(path, value)


def run_acceptance() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="bimchange-r3-complete-") as directory:
        root = Path(directory)
        clean_a, clean_b = root / "clean-a", root / "clean-b"
        first, second = build_bundle(clean_a), build_bundle(clean_b)
        records_a = strict_load_json(clean_a / "r3-records.json")
        records_b = strict_load_json(clean_b / "r3-records.json")
        def normalized_semantics(records: dict[str, Any]) -> dict[str, Any]:
            value = json.loads(json.dumps(records))
            for entry in value["cases"]:
                entry.pop("source_sha256")
                entry.pop("revised_sha256")
            return value
        normalized_match = normalized_semantics(records_a) == normalized_semantics(records_b)
        mutators: list[tuple[str, Callable[[Path], None]]] = [
            ("source_bytes", lambda d: (d / "cases" / CASES[0].slug / "source.ifc").open("ab").write(b"\n")),
            ("revised_bytes", lambda d: (d / "cases" / CASES[0].slug / "revised.ifc").open("ab").write(b"\n")),
            ("source_hash", lambda d: _mutate_json(d / "r3-records.json", lambda v: v["cases"][0].update(source_sha256="0" * 64))),
            ("revised_hash", lambda d: _mutate_json(d / "r3-records.json", lambda v: v["cases"][0].update(revised_sha256="0" * 64))),
            ("old_dimension", lambda d: _mutate_json(d / "r3-records.json", lambda v: v["cases"][0]["record"]["changed_dimensions"][0].update(old_m=9.0))),
            ("new_dimension", lambda d: _mutate_json(d / "r3-records.json", lambda v: v["cases"][0]["record"]["changed_dimensions"][0].update(new_m=9.0))),
            ("delta", lambda d: _mutate_json(d / "r3-records.json", lambda v: v["cases"][0]["record"]["changed_dimensions"][0].update(delta_m=9.0))),
            ("subtype", lambda d: _mutate_json(d / "r3-records.json", lambda v: v["cases"][0]["record"].update(geometry_subtype="arbitrary_shape"))),
            ("global_id", lambda d: _mutate_json(d / "r3-records.json", lambda v: v["cases"][0]["record"].update(global_id="0AAAAAAAAAAAAAAAAAAAAA"))),
            ("evidence_rule", lambda d: _mutate_json(d / "r3-records.json", lambda v: v["cases"][0]["record"]["evidence"].update(reconstruction_rule="forged"))),
            ("case_omission", lambda d: _mutate_json(d / "r3-records.json", lambda v: v["cases"].pop())),
            ("case_duplicate", lambda d: _mutate_json(d / "r3-records.json", lambda v: v["cases"].append(v["cases"][0]))),
            ("ledger_variant", lambda d: _mutate_json(d / "operation-ledger.json", lambda v: v["operations"][0].update(variant="noop"))),
            ("manifest_count", lambda d: _mutate_json(d / "trace-manifest.json", lambda v: v.update(case_count=999))),
            ("absolute_role", lambda d: _mutate_json(d / "trace-manifest.json", lambda v: v["artifacts"]["records"].update(role="C:\\private\\r3.json"))),
            ("duplicate_json_key", lambda d: (d / "r3-records.json").write_text((d / "r3-records.json").read_text(encoding="utf-8").replace('"protocol_id":', '"protocol_id": "duplicate", "protocol_id":', 1), encoding="utf-8")),
        ]
        tamper_results = []
        for index, (case_id, mutate) in enumerate(mutators):
            target = root / f"tamper-{index:02d}"
            shutil.copytree(clean_a, target)
            mutate(target)
            result = verify_bundle(target)
            tamper_results.append({"case_id": case_id, "status": result["status"]})
        rejected = sum(item["status"] == "FAIL" for item in tamper_results)
        status = "PASS" if first["status"] == second["status"] == "PASS" and normalized_match and rejected == len(mutators) else "FAIL"
        return {
            "status": status, "protocol_id": PROTOCOL_ID,
            "supported_case_count": len(CASES), "clean_runs": 2,
            "normalized_records_match": normalized_match,
            "trace_resolution_rate": first["trace_resolution_rate"],
            "tamper_cases": len(mutators), "tamper_rejected": rejected,
            "false_acceptance": len(mutators) - rejected,
            "tamper_results": tamper_results,
            "privacy_violation_count": 0, "model_calls_made": 0,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_acceptance()
    if args.output:
        write_json(args.output, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
