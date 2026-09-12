"""Failure-closed acceptance checks for the bounded R4 viewer proof."""

from __future__ import annotations

import argparse
import copy
import json
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath

import ifcopenshell
import jsonschema

from bimchange_agent.r4_glb import read_glb_document
from .proof import LEDGER_PATH, PROTOCOL_PATH, ROOT, build_bundle, load_json, sha256


SCHEMA_PATH = ROOT / "spatial-context.schema.json"
WINDOWS_ABSOLUTE = re.compile(r"(?i)(?:^|[\"'])[a-z]:[/\\]")
EXTERNAL_URL = re.compile(r"(?i)https?://")


class R4AcceptanceError(ValueError):
    """Raised whenever the proof cannot satisfy its frozen contract."""


def _safe_path(bundle: Path, value: str) -> Path:
    posix = PurePosixPath(value)
    if posix.is_absolute() or ".." in posix.parts or ":" in value or "\\" in value:
        raise R4AcceptanceError(f"Unsafe relative path: {value}")
    candidate = (bundle / Path(*posix.parts)).resolve()
    if bundle.resolve() not in candidate.parents:
        raise R4AcceptanceError(f"Path escapes proof bundle: {value}")
    return candidate


def _review_mark(element) -> str:
    pset = next(
        relation.RelatingPropertyDefinition
        for relation in element.IsDefinedBy
        if relation.is_a("IfcRelDefinesByProperties")
        and relation.RelatingPropertyDefinition.Name == "Pset_R4Proof"
    )
    prop = next(item for item in pset.HasProperties if item.Name == "ReviewMark")
    return prop.NominalValue.wrappedValue


def _optional_by_guid(model: ifcopenshell.file, global_id: str):
    try:
        return model.by_guid(global_id)
    except RuntimeError:
        return None


def _validate_fixture_facts(bundle: Path, manifest: dict, ledger: dict) -> None:
    source = ifcopenshell.open(_safe_path(bundle, manifest["inputs"]["source"]["file"]))
    revised = ifcopenshell.open(_safe_path(bundle, manifest["inputs"]["revised"]["file"]))
    changes = {item["change_type"]: item for item in ledger["changes"]}
    deleted = changes["deleted"]["global_id"]
    added = changes["added"]["global_id"]
    modified = changes["property_modified"]["global_id"]
    if _optional_by_guid(source, deleted) is None or _optional_by_guid(revised, deleted) is not None:
        raise R4AcceptanceError("Deleted target state does not match the ledger")
    if _optional_by_guid(source, added) is not None or _optional_by_guid(revised, added) is None:
        raise R4AcceptanceError("Added target state does not match the ledger")
    if _review_mark(source.by_guid(modified)) != "source":
        raise R4AcceptanceError("Source property control is invalid")
    if _review_mark(revised.by_guid(modified)) != "revised":
        raise R4AcceptanceError("Revised property control is invalid")


def validate_bundle(bundle: Path, *, manifest_override: dict | None = None) -> dict:
    bundle = bundle.expanduser().resolve()
    manifest = manifest_override or load_json(bundle / "manifest.json")
    protocol = load_json(PROTOCOL_PATH)
    ledger = load_json(LEDGER_PATH)
    try:
        jsonschema.Draft202012Validator(load_json(SCHEMA_PATH)).validate(manifest)
    except jsonschema.ValidationError as error:
        raise R4AcceptanceError(f"Manifest schema rejected: {error.message}") from error

    if manifest["protocol_version"] != protocol["protocol_version"]:
        raise R4AcceptanceError("Protocol version mismatch")
    for role in ("source", "revised"):
        item = manifest["inputs"][role]
        if item["role"] != role:
            raise R4AcceptanceError(f"Input role mismatch: {role}")
        path = _safe_path(bundle, item["file"])
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise R4AcceptanceError(f"Input hash mismatch: {role}")
        if ifcopenshell.open(path).schema != "IFC4":
            raise R4AcceptanceError(f"Input schema mismatch: {role}")

    expected_changes = {item["change_id"]: item for item in ledger["changes"]}
    if {item["change_id"] for item in manifest["scenes"]} != set(expected_changes):
        raise R4AcceptanceError("Scene set does not match the frozen ledger")
    changed_global_ids = {item["global_id"] for item in ledger["changes"]}
    colours = protocol["colours"]
    maximum_distance = protocol["context_policy"]["maximum_distance_m"]
    maximum_neighbours = protocol["context_policy"]["maximum_neighbours"]

    for scene in manifest["scenes"]:
        expected = expected_changes[scene["change_id"]]
        expected_role = protocol["scene_selection"][expected["change_type"]]
        if scene["change_type"] != expected["change_type"]:
            raise R4AcceptanceError("Scene change type mismatch")
        if scene["target_global_id"] != expected["global_id"]:
            raise R4AcceptanceError("Scene target GlobalId mismatch")
        if scene["selected_ifc_role"] != expected_role:
            raise R4AcceptanceError("Scene selected IFC role mismatch")
        if scene["highlight_colour"] != colours[scene["change_type"]]:
            raise R4AcceptanceError("Scene highlight colour mismatch")
        path = _safe_path(bundle, scene["file"])
        if not path.is_file() or sha256(path) != scene["sha256"]:
            raise R4AcceptanceError("Scene hash mismatch")
        if path.stat().st_size > protocol["budgets"]["maximum_scene_glb_bytes"]:
            raise R4AcceptanceError("Scene GLB exceeds the frozen byte budget")

        records = scene["nodes"]
        global_ids = [item["global_id"] for item in records]
        if len(global_ids) != len(set(global_ids)):
            raise R4AcceptanceError("Scene manifest GlobalIds are not unique")
        targets = [item for item in records if item["role"] == "target"]
        if len(targets) != 1 or targets[0]["global_id"] != scene["target_global_id"]:
            raise R4AcceptanceError("Scene manifest target cardinality is not one")
        contexts = [item for item in records if item["role"] == "context"]
        if len(contexts) > maximum_neighbours:
            raise R4AcceptanceError("Scene has too many context nodes")
        if len(records) > protocol["budgets"]["maximum_scene_elements"]:
            raise R4AcceptanceError("Scene has too many elements")
        for item in contexts:
            if item["global_id"] in changed_global_ids:
                raise R4AcceptanceError("Another changed target leaked into context")
            if item["storey_global_id"] != targets[0]["storey_global_id"]:
                raise R4AcceptanceError("Cross-storey context leaked into the scene")
            if item["distance_m"] > maximum_distance:
                raise R4AcceptanceError("Out-of-radius context leaked into the scene")

        document = read_glb_document(path)
        glb_nodes = [item for item in document.get("nodes", []) if "mesh" in item]
        glb_extras = [item.get("extras", {}) for item in glb_nodes]
        glb_global_ids = [item.get("global_id") for item in glb_extras]
        if len(glb_global_ids) != len(set(glb_global_ids)):
            raise R4AcceptanceError("GLB node GlobalIds are not unique")
        if sorted(glb_global_ids) != sorted(global_ids):
            raise R4AcceptanceError("GLB nodes do not match manifest nodes")
        target_extras = [
            item
            for item in glb_extras
            if item.get("global_id") == scene["target_global_id"]
            and item.get("role") == "target"
        ]
        if len(target_extras) != 1:
            raise R4AcceptanceError("GLB target mapping is not uniquely resolved")
        for item in glb_extras:
            if item.get("ifc_role") != expected_role:
                raise R4AcceptanceError("GLB contains a wrong-version role")
            manifest_node = next(
                candidate for candidate in records if candidate["global_id"] == item["global_id"]
            )
            for key in ("entity_type", "storey_global_id", "storey_name", "role"):
                if item.get(key) != manifest_node[key]:
                    raise R4AcceptanceError(f"GLB metadata mismatch: {key}")

    for value in [manifest["viewer"]["entrypoint"], *manifest["viewer"]["local_assets"]]:
        if not _safe_path(bundle, value).is_file():
            raise R4AcceptanceError(f"Missing local viewer asset: {value}")
    authored_text = "\n".join(
        _safe_path(bundle, value).read_text(encoding="utf-8")
        for value in (
            manifest["viewer"]["entrypoint"],
            "viewer/app.js",
            "viewer/styles.css",
        )
    )
    if EXTERNAL_URL.search(authored_text) or "cdn.jsdelivr" in authored_text.lower():
        raise R4AcceptanceError("Viewer contains an external URL or CDN reference")
    serialized = json.dumps(manifest, ensure_ascii=False)
    if WINDOWS_ABSOLUTE.search(serialized):
        raise R4AcceptanceError("Manifest contains an absolute Windows path")
    if any(marker in serialized.lower() for marker in ("api_key", "sk-proj-", "bearer ")):
        raise R4AcceptanceError("Manifest contains a credential marker")

    payload_bytes = sum(
        path.stat().st_size
        for path in bundle.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    )
    if payload_bytes != manifest["metrics"]["payload_bytes_excluding_manifest"]:
        raise R4AcceptanceError("Payload byte count mismatch")
    if payload_bytes > protocol["budgets"]["maximum_complete_bundle_bytes"]:
        raise R4AcceptanceError("Proof bundle exceeds the frozen byte budget")
    _validate_fixture_facts(bundle, manifest, ledger)
    return {
        "scene_count": len(manifest["scenes"]),
        "unique_target_resolution_rate": 1.0,
        "payload_bytes_excluding_manifest": payload_bytes,
        "model_or_api_calls": 0,
        "privacy_violations": 0,
    }


def _write_manifest(bundle: Path, manifest: dict) -> None:
    (bundle / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _run_tamper_matrix(pristine_bundle: Path) -> list[dict]:
    cases = []

    def reject(name: str, mutate) -> None:
        with tempfile.TemporaryDirectory(prefix=f"r4-tamper-{name}-") as temporary:
            candidate = Path(temporary) / "bundle"
            shutil.copytree(pristine_bundle, candidate)
            manifest = load_json(candidate / "manifest.json")
            mutate(candidate, manifest)
            _write_manifest(candidate, manifest)
            try:
                validate_bundle(candidate)
            except (R4AcceptanceError, ValueError, json.JSONDecodeError) as error:
                cases.append({"case": name, "rejected": True, "reason": str(error)})
                return
            raise AssertionError(f"Tamper case was incorrectly accepted: {name}")

    reject("input_hash", lambda _, m: m["inputs"]["source"].__setitem__("sha256", "0" * 64))
    reject("scene_hash", lambda _, m: m["scenes"][0].__setitem__("sha256", "0" * 64))
    reject(
        "target_global_id",
        lambda _, m: m["scenes"][0].__setitem__(
            "target_global_id", m["scenes"][0]["nodes"][1]["global_id"]
        ),
    )
    reject(
        "target_node_omission",
        lambda _, m: m["scenes"][0].__setitem__(
            "nodes", [item for item in m["scenes"][0]["nodes"] if item["role"] != "target"]
        ),
    )
    reject(
        "target_node_duplication",
        lambda _, m: m["scenes"][0]["nodes"].append(copy.deepcopy(m["scenes"][0]["nodes"][0])),
    )
    reject(
        "selected_ifc_role",
        lambda _, m: m["scenes"][0].__setitem__("selected_ifc_role", "revised"),
    )
    reject(
        "highlight_colour",
        lambda _, m: m["scenes"][0].__setitem__("highlight_colour", "#FFFFFF"),
    )
    reject(
        "absolute_path",
        lambda _, m: m["viewer"].__setitem__("entrypoint", "C:/private/viewer.html"),
    )
    reject(
        "external_url",
        lambda _, m: m["viewer"].__setitem__("entrypoint", "https://example.invalid/viewer"),
    )

    def tamper_glb(bundle: Path, manifest: dict) -> None:
        path = _safe_path(bundle, manifest["scenes"][0]["file"])
        path.write_bytes(path.read_bytes() + b"tamper")

    reject("glb_payload", tamper_glb)
    return cases


def _relative_files(root: Path) -> list[Path]:
    return sorted(path.relative_to(root) for path in root.rglob("*") if path.is_file())


def run_acceptance(output_directory: Path) -> dict:
    output_directory = output_directory.expanduser().resolve()
    if output_directory.exists():
        raise FileExistsError(f"Refusing to overwrite R4 acceptance output: {output_directory}")
    output_directory.mkdir(parents=True)
    first = build_bundle(output_directory / "bundle")
    with tempfile.TemporaryDirectory(prefix="r4-repeat-") as temporary:
        second = build_bundle(Path(temporary) / "bundle")
        first_validation = validate_bundle(first.bundle)
        second_validation = validate_bundle(second.bundle)
        first_files = _relative_files(first.bundle)
        second_files = _relative_files(second.bundle)
        if first_files != second_files:
            raise AssertionError("Clean R4 builds produced different file sets")
        differing = [
            path.as_posix()
            for path in first_files
            if (first.bundle / path).read_bytes() != (second.bundle / path).read_bytes()
        ]
        if differing:
            raise AssertionError(f"Clean R4 builds were not byte-identical: {differing}")
        second_seconds = second.build_seconds

    protocol = load_json(PROTOCOL_PATH)
    if max(first.build_seconds, second_seconds) > protocol["budgets"]["maximum_clean_build_seconds"]:
        raise AssertionError("Clean build exceeded the frozen time budget")
    tamper = _run_tamper_matrix(first.bundle)
    report = {
        "protocol_version": protocol["protocol_version"],
        "status": "STANDALONE_TECHNICAL_GATE_PASSED_BROWSER_QA_PENDING",
        "clean_builds": 2,
        "byte_identical_file_count": len(first_files),
        "build_seconds": [round(first.build_seconds, 6), round(second_seconds, 6)],
        "validation": first_validation,
        "repeat_validation": second_validation,
        "tamper_rejected": sum(item["rejected"] for item in tamper),
        "tamper_total": len(tamper),
        "false_acceptance": 0,
        "tamper_cases": tamper,
        "browser_qa": "PENDING",
        "qt_webengine_product_slice": "NOT_PERMITTED",
    }
    (output_directory / "acceptance-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_directory", type=Path)
    args = parser.parse_args()
    report = run_acceptance(args.output_directory)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
