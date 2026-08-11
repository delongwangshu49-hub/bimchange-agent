"""Generate the Gate 4 neutral-code to frozen-execution mapping offline."""

from __future__ import annotations

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
    SCHEDULE_PATH,
    artifact_sha256,
    canonical_hash,
    load_json,
    sha256_file,
    write_json,
)
from generate_gate4_blind_audit_packet import (  # noqa: E402
    BLIND_PACKET_PATH,
    EXPECTED_SCHEDULE_SHA256,
    EXPECTED_SELECTION_SHA256,
    RESULT_MANIFEST_PATH,
    RESULTS_ROOT,
    build_blind_packet,
    build_result_manifest,
    require_equal,
    selected_executions,
)


EXPECTED_IMPORTED_PACKET_SHA256 = (
    "1d3a40deadc99f337df6ee42af6589c108e3073afe6b38cbe3c903dba930df10"
)
EXPECTED_RESULT_MANIFEST_SHA256 = (
    "5904ef49e61e196ecc230369d959b2598742c6acdf10aeb739f38dffb4bef8a1"
)
MAPPING_PATH = RESULTS_ROOT / "workflow-repetition-mapping.json"


def relative(path: Path) -> str:
    return path.relative_to(REPOSITORY_ROOT).as_posix()


def without_reviews(packet: dict[str, Any]) -> dict[str, Any]:
    """Return the blinded packet with only the mutable review fields removed."""
    projected = {key: value for key, value in packet.items() if key != "entries"}
    projected["entries"] = [
        {key: value for key, value in entry.items() if key != "review"}
        for entry in packet["entries"]
    ]
    return projected


def validate_completed_reviews(packet: dict[str, Any]) -> None:
    """Refuse to unblind until all frozen manual-review rows are complete."""
    require_equal(len(packet["entries"]), 135, "audit entry count")
    require_equal(
        [entry["audit_code"] for entry in packet["entries"]],
        [f"A{index:03d}" for index in range(1, 136)],
        "neutral audit codes",
    )
    for entry in packet["entries"]:
        review = entry["review"]
        require_equal(review["review_complete"], True, f"{entry['audit_code']} review")
        if entry["candidate_available"]:
            if not review["atomic_claims"]:
                raise ValueError(f"{entry['audit_code']} has no audited atomic claims")
        else:
            require_equal(
                review["atomic_claims"], [], f"{entry['audit_code']} failure claims"
            )


def validate_frozen_inputs() -> tuple[dict[str, Any], dict[str, Any], str]:
    """Rebuild every non-review input before deriving the mapping."""
    verify_gate4_foundation()
    require_equal(
        artifact_sha256(SCHEDULE_PATH), EXPECTED_SCHEDULE_SHA256, "schedule hash"
    )
    schedule = load_json(SCHEDULE_PATH)
    audit = schedule["audit_selection"]
    require_equal(
        canonical_hash(audit["all_selected_question_ids"]),
        EXPECTED_SELECTION_SHA256,
        "audit selection hash",
    )

    manifest = load_json(RESULT_MANIFEST_PATH)
    require_equal(manifest, build_result_manifest(), "result manifest")
    manifest_sha256 = artifact_sha256(RESULT_MANIFEST_PATH)
    require_equal(
        manifest_sha256, EXPECTED_RESULT_MANIFEST_SHA256, "result manifest hash"
    )

    packet = load_json(BLIND_PACKET_PATH)
    require_equal(
        artifact_sha256(BLIND_PACKET_PATH),
        EXPECTED_IMPORTED_PACKET_SHA256,
        "completed audit packet hash",
    )
    validate_completed_reviews(packet)
    expected_blank_packet = build_blind_packet(manifest_sha256)
    require_equal(
        without_reviews(packet),
        without_reviews(expected_blank_packet),
        "frozen non-review packet projection",
    )
    return schedule, packet, manifest_sha256


def build_mapping() -> dict[str, Any]:
    schedule, packet, manifest_sha256 = validate_frozen_inputs()
    executions = selected_executions(schedule, manifest_sha256)
    require_equal(len(executions), len(packet["entries"]), "mapping row count")

    rows: list[dict[str, Any]] = []
    for entry, execution in zip(packet["entries"], executions, strict=True):
        require_equal(
            entry["question_id"], execution["question_id"], "mapped question ID"
        )
        execution_id = execution["execution_id"]
        run_path = RESULTS_ROOT / "primary" / execution_id / "run.json"
        candidate_path = RESULTS_ROOT / "primary" / execution_id / "candidate.json"
        require_equal(candidate_path.is_file(), entry["candidate_available"], "candidate")
        row = {
            "audit_code": entry["audit_code"],
            "execution_id": execution_id,
            "ordinal": execution["ordinal"],
            "repetition": execution["repetition"],
            "workflow": execution["workflow"],
            "question_position": execution["question_position"],
            "question_id": execution["question_id"],
            "category": entry["category"],
            "candidate_available": entry["candidate_available"],
            "run_sha256": sha256_file(run_path),
            "candidate_sha256": sha256_file(candidate_path)
            if candidate_path.is_file()
            else None,
        }
        rows.append(row)

    return {
        "schema_version": "0.1.0",
        "dataset_id": "gate4-controlled-heldout-v0.1.0",
        "split": "held_out",
        "status": "UNBLINDED_AFTER_ALL_HUMAN_LABELS_SAVED",
        "completed_audit_packet_sha256": EXPECTED_IMPORTED_PACKET_SHA256,
        "result_manifest_sha256": manifest_sha256,
        "schedule_sha256": EXPECTED_SCHEDULE_SHA256,
        "audit_selection_sha256": EXPECTED_SELECTION_SHA256,
        "mapping_row_count": len(rows),
        "candidate_available_count": sum(row["candidate_available"] for row in rows),
        "experimental_failure_count": sum(
            not row["candidate_available"] for row in rows
        ),
        "entries": rows,
        "reference_answers_read": False,
        "scoring_performed": False,
        "post_run_audit_generated": False,
        "model_calls_made": 0,
    }


def main() -> None:
    mapping = build_mapping()
    write_json(MAPPING_PATH, mapping)
    print(
        json.dumps(
            {
                "status": "PASS",
                "mapping": relative(MAPPING_PATH),
                "mapping_sha256": artifact_sha256(MAPPING_PATH),
                "mapping_row_count": mapping["mapping_row_count"],
                "candidate_available_count": mapping["candidate_available_count"],
                "experimental_failure_count": mapping["experimental_failure_count"],
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
