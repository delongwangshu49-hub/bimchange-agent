"""Freeze Gate 4 primary outputs and build the preselected blinded audit packet."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.gate4_foundation import verify_gate4_foundation  # noqa: E402
from bimchange_agent.gate4_orchestration import (  # noqa: E402
    PRE_RUN_AUDIT_PATH,
    SCHEDULE_PATH,
    artifact_sha256,
    canonical_hash,
    foundation_paths,
    load_json,
    sha256_file,
    write_json,
)


RESULTS_ROOT = (
    REPOSITORY_ROOT
    / "evals/results/held_out/gate4-controlled-heldout-v0.1.0"
)
CHECKPOINT_PATH = RESULTS_ROOT / "checkpoint.json"
RESULT_MANIFEST_PATH = RESULTS_ROOT / "result-freeze-manifest.json"
BLIND_PACKET_PATH = RESULTS_ROOT / "blinded-audit-packet.json"
EXPECTED_SCHEDULE_SHA256 = (
    "92360439cef1797615bdb964020cfa92ab8e345a22dfe07b45f5883336db9750"
)
EXPECTED_SELECTION_SHA256 = (
    "907ead457eb5a0200ce32467e4aa0b05cdd74b1132da6daad9ae0b812e0a7810"
)
BANNED_PACKET_KEYS = {
    "execution_id",
    "ordinal",
    "workflow",
    "repetition",
    "question_position",
    "model_config",
    "metadata",
    "frozen_runtime_mapping",
    "raw_provider_responses",
}


def relative(path: Path) -> str:
    return path.relative_to(REPOSITORY_ROOT).as_posix()


def require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def result_files() -> list[Path]:
    files = [CHECKPOINT_PATH]
    for ordinal in range(1, 361):
        directory = RESULTS_ROOT / "primary" / f"gate4-primary-{ordinal:03d}"
        files.append(directory / "run.json")
        candidate = directory / "candidate.json"
        if candidate.is_file():
            files.append(candidate)
    return files


def build_result_manifest() -> dict[str, Any]:
    checkpoint = load_json(CHECKPOINT_PATH)
    require_equal(len(checkpoint["completed_execution_ids"]), 360, "checkpoint count")
    expected_ids = [f"gate4-primary-{ordinal:03d}" for ordinal in range(1, 361)]
    require_equal(
        checkpoint["completed_execution_ids"], expected_ids, "checkpoint sequence"
    )
    require_equal(
        checkpoint["schedule_sha256"], EXPECTED_SCHEDULE_SHA256, "schedule hash"
    )

    entries: list[dict[str, Any]] = []
    candidate_count = 0
    for path in result_files():
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.name == "candidate.json":
            candidate_count += 1
        entries.append(
            {
                "path": relative(path),
                "sha256": sha256_file(path),
                "byte_size": path.stat().st_size,
            }
        )
    require_equal(candidate_count, 348, "candidate count")
    manifest = {
        "schema_version": "0.1.0",
        "dataset_id": "gate4-controlled-heldout-v0.1.0",
        "split": "held_out",
        "status": "PRIMARY_RESULTS_FROZEN_BEFORE_SCORING_OR_AUDIT",
        "schedule_sha256": EXPECTED_SCHEDULE_SHA256,
        "checkpoint_sha256": sha256_file(CHECKPOINT_PATH),
        "primary_execution_count": 360,
        "candidate_count": candidate_count,
        "experimental_failure_count": 360 - candidate_count,
        "file_count": len(entries),
        "files": entries,
        "files_canonical_sha256": canonical_hash(entries),
        "reference_answers_read": False,
        "scoring_performed": False,
        "post_run_audit_generated": False,
        "model_calls_made": 0,
    }
    return manifest


def blinding_order_key(
    selection_seed: str, result_manifest_sha256: str, execution_id: str
) -> str:
    value = f"{selection_seed}:{result_manifest_sha256}:{execution_id}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def selected_executions(
    schedule: dict[str, Any], result_manifest_sha256: str
) -> list[dict[str, Any]]:
    audit = schedule["audit_selection"]
    require_equal(audit["selection_sha256"], EXPECTED_SELECTION_SHA256, "selection hash")
    selected_ids = set(audit["all_selected_question_ids"])
    require_equal(len(selected_ids), 15, "selected question count")
    executions = [
        execution
        for execution in schedule["executions"]
        if execution["question_id"] in selected_ids
    ]
    require_equal(len(executions), 135, "selected execution count")
    counts = {
        question_id: sum(
            execution["question_id"] == question_id for execution in executions
        )
        for question_id in selected_ids
    }
    require_equal(set(counts.values()), {9}, "executions per selected question")
    return sorted(
        executions,
        key=lambda item: blinding_order_key(
            audit["selection_seed"], result_manifest_sha256, item["execution_id"]
        ),
    )


def blank_review() -> dict[str, Any]:
    return {
        "atomic_claims": [],
        "evidence_references_verified": None,
        "safety_overreach": None,
        "failure_categories": [],
        "review_notes": None,
        "review_complete": False,
    }


def build_blind_packet(result_manifest_sha256: str) -> dict[str, Any]:
    schedule = load_json(SCHEDULE_PATH)
    questions_artifact = load_json(foundation_paths()["questions"])
    questions = {
        question["question_id"]: question
        for question in questions_artifact["questions"]
    }
    pre_run_audit = load_json(PRE_RUN_AUDIT_PATH)
    executions = selected_executions(schedule, result_manifest_sha256)

    entries: list[dict[str, Any]] = []
    missing_candidates = 0
    for index, execution in enumerate(executions, start=1):
        question = questions[execution["question_id"]]
        directory = RESULTS_ROOT / "primary" / execution["execution_id"]
        candidate_path = directory / "candidate.json"
        if candidate_path.is_file():
            candidate = load_json(candidate_path)
            require_equal(len(candidate["answers"]), 1, "candidate answer count")
            answer = candidate["answers"][0]
            require_equal(answer["question_id"], question["question_id"], "question ID")
            payload: dict[str, Any] = {
                "candidate_available": True,
                "model_output": answer,
            }
        else:
            missing_candidates += 1
            run = load_json(directory / "run.json")
            require_equal(run.get("status"), "EXPERIMENTAL_FAILURE", "failure status")
            require_equal(run.get("candidate_persisted"), False, "candidate flag")
            payload = {
                "candidate_available": False,
                "experimental_failure": {
                    "status": "EXPERIMENTAL_FAILURE",
                    "category": run["failure"]["category"],
                    "candidate_persisted": False,
                    "retry_allowed": False,
                    "retry_performed": False,
                },
            }
        entries.append(
            {
                "audit_code": f"A{index:03d}",
                "question_id": question["question_id"],
                "category": question["category"],
                "question": question["question"],
                **payload,
                "review": blank_review(),
            }
        )

    packet = {
        "schema_version": "0.1.0",
        "dataset_id": "gate4-controlled-heldout-v0.1.0",
        "split": "held_out",
        "audit_status": "AWAITING_HUMAN_LABELS",
        "mapping_status": "WITHHELD_UNTIL_ALL_LABELS_ARE_SAVED",
        "result_manifest_sha256": result_manifest_sha256,
        "audit_selection_sha256": EXPECTED_SELECTION_SHA256,
        "selected_question_count": 15,
        "audited_answer_count": len(entries),
        "candidate_available_count": len(entries) - missing_candidates,
        "experimental_failure_count": missing_candidates,
        "allowed_claim_labels": ["supported", "unsupported", "indeterminate"],
        "allowed_failure_categories": pre_run_audit["failure_categories"],
        "review_instructions": {
            "atomic_claims": "Split each available answer into atomic claims and label every claim.",
            "evidence": "Verify every cited evidence reference against the supplied held-out evidence before completing the item.",
            "safety": "Record any unsupported safety, compliance, responsibility, priority, or constructability conclusion.",
            "failures": "A missing candidate is an auditable experimental failure; do not invent an answer.",
            "unblinding": "Do not reconstruct or reveal workflow/repetition mapping before all 135 reviews are saved.",
        },
        "entries": entries,
        "workflow_repetition_mapping_present": False,
        "reference_answers_present": False,
        "scores_present": False,
        "post_run_audit_generated": False,
        "model_calls_made": 0,
    }
    return packet


def find_banned_keys(value: Any, location: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_location = f"{location}.{key}"
            if key in BANNED_PACKET_KEYS:
                findings.append(child_location)
            findings.extend(find_banned_keys(child, child_location))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(find_banned_keys(child, f"{location}[{index}]"))
    return findings


def main() -> None:
    foundation = verify_gate4_foundation()
    require_equal(artifact_sha256(SCHEDULE_PATH), EXPECTED_SCHEDULE_SHA256, "schedule")
    require_equal(
        foundation_paths()["post_run_audit"].exists(), False, "post-run audit file"
    )
    manifest = build_result_manifest()
    write_json(RESULT_MANIFEST_PATH, manifest)
    manifest_sha256 = artifact_sha256(RESULT_MANIFEST_PATH)
    packet = build_blind_packet(manifest_sha256)
    banned = find_banned_keys(packet)
    require_equal(banned, [], "banned blinded-packet keys")
    write_json(BLIND_PACKET_PATH, packet)
    print(
        json.dumps(
            {
                "status": "PASS",
                "foundation_status": foundation["status"],
                "result_manifest": relative(RESULT_MANIFEST_PATH),
                "result_manifest_sha256": manifest_sha256,
                "blind_packet": relative(BLIND_PACKET_PATH),
                "blind_packet_sha256": artifact_sha256(BLIND_PACKET_PATH),
                "primary_execution_count": 360,
                "candidate_count": 348,
                "experimental_failure_count": 12,
                "audited_answer_count": 135,
                "workflow_repetition_mapping_present": False,
                "reference_answers_read": False,
                "scoring_performed": False,
                "post_run_audit_generated": False,
                "model_calls_made": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
