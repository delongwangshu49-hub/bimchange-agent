"""Prepare and verify neutral N=1 review packets without executing the trials."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from bimchange_agent.product_core import (
    CHANGE_RECORD_FILE_NAME,
    RAW_DIFF_FILE_NAME,
    diff_ifc_pair,
)

from .acceptance import DEFAULT_REVISED, DEFAULT_SOURCE
from .traceability import (
    MANIFEST_FILE_NAME,
    generate_trace_manifest,
    privacy_violations,
    sha256_file,
    strict_load_json,
    verify_trace_manifest,
    write_json,
)


ROOT = Path(__file__).resolve().parent
PROTOCOL_PATH = ROOT / "n1-review-protocol.json"
LOG_TEMPLATE_PATH = ROOT / "n1-review-log.template.json"
PACKAGE_MANIFEST = "prepared-package-manifest.json"
PROMPTS = {
    "N1-T01": (
        "Verify the deleted Change Record. Report its GlobalId, entity type, "
        "source/revised presence, building storey, old snapshot, and raw section."
    ),
    "N1-T02": (
        "Verify the added Change Record. Report its GlobalId, entity type, "
        "source/revised presence, spatial container, new snapshot, and trace ID."
    ),
    "N1-T03": (
        "Verify the property-modified Change Record. Report its GlobalId, property "
        "set, property name, old value, new value, and raw property path."
    ),
    "N1-T04": (
        "Verify the deleted record by following its trace entry back to the raw "
        "section and source IFC. Report the reconstructed facts and digest bindings."
    ),
    "N1-T05": (
        "Manually decide whether the added record has complete evidence across the "
        "Change Record, raw result, source IFC, and revised IFC. Explain the decision."
    ),
    "N1-T06": (
        "Verify the property-modified record using the trace locator, raw leaf, and "
        "both IFC roles. Report the old/new values and verifier status."
    ),
    "N1-T07": (
        "Review this controlled locator-tamper packet without a trace verifier. "
        "Decide accept or reject and identify the evidence inconsistency."
    ),
    "N1-T08": (
        "Review this controlled trace-entry-omission packet. Decide accept or reject "
        "and explain the verifier failure without consulting an answer key."
    ),
}


def _copy(path: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, destination)


def _record_by_type(records: dict[str, Any], change_type: str) -> dict[str, Any]:
    return next(
        record for record in records["changes"] if record["change_type"] == change_type
    )


def _entry_by_type(manifest: dict[str, Any], change_type: str) -> dict[str, Any]:
    return next(
        entry for entry in manifest["entries"] if entry["change_type"] == change_type
    )


def _answer_key(records: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    added = _record_by_type(records, "added")
    deleted = _record_by_type(records, "deleted")
    modified = _record_by_type(records, "property_modified")
    added_entry = _entry_by_type(manifest, "added")
    deleted_entry = _entry_by_type(manifest, "deleted")
    modified_entry = _entry_by_type(manifest, "property_modified")
    return {
        "protocol_id": "r1-n1-review-diagnostic-0.1.0",
        "participant_must_not_open_before_all_trials_complete": True,
        "answers": {
            "N1-T01": {
                "record": deleted,
                "source_presence": True,
                "revised_presence": False,
                "raw_section": "deleted",
            },
            "N1-T02": {
                "record": added,
                "source_presence": False,
                "revised_presence": True,
                "trace_id": added_entry["trace_id"],
            },
            "N1-T03": {
                "record": modified,
                "property_path": modified_entry["raw_evidence"]["locator"][
                    "property_path"
                ],
            },
            "N1-T04": {
                "record": deleted,
                "trace_entry": deleted_entry,
            },
            "N1-T05": {"record": added, "decision": "complete"},
            "N1-T06": {
                "record": modified,
                "trace_entry": modified_entry,
                "verifier_status": "PASS",
            },
            "N1-T07": {
                "decision": "reject",
                "diagnostic": "evidence_locator_missing",
            },
            "N1-T08": {
                "decision": "reject",
                "diagnostic": "change_record_digest_mismatch",
            },
        },
        "model_calls_made": 0,
    }


def _blank_log(protocol: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    trial_template = template["trial_template"]
    trials = []
    for scheduled in protocol["schedule"]:
        trial = json.loads(json.dumps(trial_template))
        trial["trial_id"] = scheduled["trial_id"]
        trial["condition"] = scheduled["condition"]
        trials.append(trial)
    result = dict(template)
    result.pop("trial_template")
    result["trials"] = trials
    return result


def _task_document(scheduled: dict[str, str]) -> dict[str, Any]:
    return {
        "protocol_id": "r1-n1-review-diagnostic-0.1.0",
        "trial_id": scheduled["trial_id"],
        "condition": scheduled["condition"],
        "task_type": scheduled["task_type"],
        "prompt": PROMPTS[scheduled["trial_id"]],
        "required_response_fields": [
            "answer",
            "accept_or_reject_when_applicable",
            "evidence_steps",
            "final_reason",
        ],
        "answer_key_present": False,
        "model_calls_made": 0,
    }


def _write_packet_manifest(packet: Path) -> None:
    files = {
        path.relative_to(packet).as_posix(): sha256_file(path)
        for path in sorted(packet.rglob("*"))
        if path.is_file() and path.name != "packet-manifest.json"
    }
    write_json(
        packet / "packet-manifest.json",
        {
            "status": "PREPARED_NOT_EXECUTED",
            "files": files,
            "answer_key_present": False,
            "model_calls_made": 0,
        },
    )


def prepare_n1_packets(output: Path) -> dict[str, Any]:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    protocol = strict_load_json(PROTOCOL_PATH)
    template = strict_load_json(LOG_TEMPLATE_PATH)
    with tempfile.TemporaryDirectory(prefix="bimchange-r1-n1-base-") as directory:
        base = Path(directory)
        diff_ifc_pair(DEFAULT_SOURCE, DEFAULT_REVISED, base)
        records_path = base / CHANGE_RECORD_FILE_NAME
        raw_path = base / RAW_DIFF_FILE_NAME
        manifest_path = base / MANIFEST_FILE_NAME
        records = strict_load_json(records_path)
        raw = strict_load_json(raw_path)
        manifest = generate_trace_manifest(
            DEFAULT_SOURCE, DEFAULT_REVISED, records_path, raw_path
        )
        write_json(manifest_path, manifest)
        clean_report = verify_trace_manifest(
            manifest_path,
            DEFAULT_SOURCE,
            DEFAULT_REVISED,
            records_path,
            raw_path,
        )
        assert clean_report["status"] == "PASS"

        participant = output / "participant"
        coordinator = output / "coordinator-do-not-open-before-completion"
        participant.mkdir()
        coordinator.mkdir()
        write_json(participant / "session-log.json", _blank_log(protocol, template))
        write_json(coordinator / "answer-key.json", _answer_key(records, manifest))

        for index, scheduled in enumerate(protocol["schedule"], start=1):
            packet = participant / f"P{index:03d}"
            packet.mkdir()
            _copy(DEFAULT_SOURCE, packet / "source.ifc")
            _copy(DEFAULT_REVISED, packet / "revised.ifc")
            packet_records = json.loads(json.dumps(records))
            packet_manifest = json.loads(json.dumps(manifest))
            if scheduled["trial_id"] == "N1-T07":
                _record_by_type(packet_records, "added")["evidence"]["selector"] = (
                    "deleted"
                )
            if scheduled["trial_id"] == "N1-T08":
                packet_manifest["entries"].pop()
                packet_manifest["summary"]["resolved_unique"] = 2
                packet_manifest["summary"]["trace_resolution_rate"] = 2 / 3
            if scheduled["trial_id"] == "N1-T07":
                write_json(packet / CHANGE_RECORD_FILE_NAME, packet_records)
            else:
                _copy(records_path, packet / CHANGE_RECORD_FILE_NAME)
            _copy(raw_path, packet / RAW_DIFF_FILE_NAME)
            if scheduled["condition"] == "B":
                if scheduled["trial_id"] == "N1-T08":
                    write_json(packet / MANIFEST_FILE_NAME, packet_manifest)
                else:
                    _copy(manifest_path, packet / MANIFEST_FILE_NAME)
                verification = verify_trace_manifest(
                    packet / MANIFEST_FILE_NAME,
                    packet / "source.ifc",
                    packet / "revised.ifc",
                    packet / CHANGE_RECORD_FILE_NAME,
                    packet / RAW_DIFF_FILE_NAME,
                )
                write_json(packet / "verifier-report.json", verification)
            write_json(packet / "task.json", _task_document(scheduled))
            _write_packet_manifest(packet)

    file_hashes = {
        path.relative_to(output).as_posix(): sha256_file(path)
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name != PACKAGE_MANIFEST
    }
    write_json(
        output / PACKAGE_MANIFEST,
        {
            "status": "PREPARED_NOT_EXECUTED",
            "protocol_id": protocol["protocol_id"],
            "packet_count": 8,
            "files": file_hashes,
            "external_ifc_files_accessed": False,
            "model_calls_made": 0,
        },
    )
    return verify_prepared_n1_packets(output)


def _contains_forbidden_task_answer(task: dict[str, Any], known_ids: set[str]) -> bool:
    serialized = json.dumps(task, ensure_ascii=False)
    return any(global_id in serialized for global_id in known_ids)


def verify_prepared_n1_packets(output: Path) -> dict[str, Any]:
    output = output.resolve()
    protocol = strict_load_json(PROTOCOL_PATH)
    package = strict_load_json(output / PACKAGE_MANIFEST)
    expected_files = package["files"]
    actual_files = {
        path.relative_to(output).as_posix(): sha256_file(path)
        for path in sorted(output.rglob("*"))
        if path.is_file() and path.name != PACKAGE_MANIFEST
    }
    assert actual_files == expected_files
    participant = output / "participant"
    answer_key = strict_load_json(
        output / "coordinator-do-not-open-before-completion" / "answer-key.json"
    )
    known_ids = {
        answer["record"]["global_id"]
        for answer in answer_key["answers"].values()
        if "record" in answer
    }
    condition_counts = {"A": 0, "B": 0}
    for index, scheduled in enumerate(protocol["schedule"], start=1):
        packet = participant / f"P{index:03d}"
        task = strict_load_json(packet / "task.json")
        assert task["trial_id"] == scheduled["trial_id"]
        assert task["condition"] == scheduled["condition"]
        assert task["answer_key_present"] is False
        assert not _contains_forbidden_task_answer(task, known_ids)
        condition_counts[scheduled["condition"]] += 1
        names = {path.name for path in packet.iterdir() if path.is_file()}
        if scheduled["condition"] == "A":
            assert MANIFEST_FILE_NAME not in names
            assert "verifier-report.json" not in names
        else:
            assert MANIFEST_FILE_NAME in names
            assert "verifier-report.json" in names
            report = strict_load_json(packet / "verifier-report.json")
            expected_status = "FAIL" if scheduled["trial_id"] == "N1-T08" else "PASS"
            assert report["status"] == expected_status
        if scheduled["trial_id"] == "N1-T07":
            records = strict_load_json(packet / CHANGE_RECORD_FILE_NAME)
            assert _record_by_type(records, "added")["evidence"]["selector"] == "deleted"
        manifest = strict_load_json(packet / "packet-manifest.json")
        assert manifest["answer_key_present"] is False
    log = strict_load_json(participant / "session-log.json")
    assert len(log["trials"]) == len(protocol["schedule"])
    assert all(
        trial["started_at"] is None
        and trial["completed_at"] is None
        and trial["answer"] is None
        for trial in log["trials"]
    )
    json_values = [
        strict_load_json(path)
        for path in output.rglob("*.json")
        if path.name != "answer-key.json"
    ]
    assert not any(privacy_violations(value) for value in json_values)
    return {
        "status": "PASS",
        "protocol_id": protocol["protocol_id"],
        "packet_count": len(protocol["schedule"]),
        "condition_counts": condition_counts,
        "condition_a_trace_files": 0,
        "condition_b_trace_files": condition_counts["B"],
        "task_answer_leakage_count": 0,
        "blank_trial_count": len(log["trials"]),
        "external_ifc_files_accessed": False,
        "privacy_violation_count": 0,
        "execution_status": "NOT_STARTED",
        "model_calls_made": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if bool(args.output) == bool(args.verify):
        parser.error("provide exactly one of --output or --verify")
    result = (
        prepare_n1_packets(args.output)
        if args.output is not None
        else verify_prepared_n1_packets(args.verify)
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
