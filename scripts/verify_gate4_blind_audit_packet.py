"""Verify the frozen Gate 4 result manifest and blinded audit packet offline."""

from __future__ import annotations

import json
from typing import Any

from generate_gate4_blind_audit_packet import (
    BLIND_PACKET_PATH,
    EXPECTED_SELECTION_SHA256,
    EXPECTED_SCHEDULE_SHA256,
    RESULT_MANIFEST_PATH,
    RESULTS_ROOT,
    artifact_sha256,
    build_blind_packet,
    build_result_manifest,
    find_banned_keys,
    foundation_paths,
    load_json,
    require_equal,
)


def verify_blank_review(review: dict[str, Any], code: str) -> None:
    require_equal(review["atomic_claims"], [], f"{code} atomic claims")
    require_equal(
        review["evidence_references_verified"], None, f"{code} evidence review"
    )
    require_equal(review["safety_overreach"], None, f"{code} safety review")
    require_equal(review["failure_categories"], [], f"{code} failure categories")
    require_equal(review["review_notes"], None, f"{code} review notes")
    require_equal(review["review_complete"], False, f"{code} review status")


def main() -> None:
    manifest = load_json(RESULT_MANIFEST_PATH)
    expected_manifest = build_result_manifest()
    require_equal(manifest, expected_manifest, "result manifest")
    require_equal(manifest["schedule_sha256"], EXPECTED_SCHEDULE_SHA256, "schedule")
    require_equal(manifest["file_count"], 709, "result file count")
    require_equal(manifest["candidate_count"], 348, "candidate count")
    require_equal(manifest["experimental_failure_count"], 12, "failure count")

    manifest_sha256 = artifact_sha256(RESULT_MANIFEST_PATH)
    packet = load_json(BLIND_PACKET_PATH)
    expected_packet = build_blind_packet(manifest_sha256)
    require_equal(packet, expected_packet, "blind packet")
    require_equal(
        packet["audit_selection_sha256"], EXPECTED_SELECTION_SHA256, "selection"
    )
    require_equal(packet["audited_answer_count"], 135, "audit entry count")
    require_equal(
        [entry["audit_code"] for entry in packet["entries"]],
        [f"A{index:03d}" for index in range(1, 136)],
        "neutral audit codes",
    )
    question_counts: dict[str, int] = {}
    for entry in packet["entries"]:
        question_counts[entry["question_id"]] = (
            question_counts.get(entry["question_id"], 0) + 1
        )
        verify_blank_review(entry["review"], entry["audit_code"])
    require_equal(len(question_counts), 15, "selected question count")
    require_equal(set(question_counts.values()), {9}, "entries per question")
    require_equal(find_banned_keys(packet), [], "banned packet keys")
    require_equal(packet["workflow_repetition_mapping_present"], False, "mapping")
    require_equal(packet["reference_answers_present"], False, "reference answers")
    require_equal(packet["scores_present"], False, "scores")
    require_equal(packet["post_run_audit_generated"], False, "post-run audit")
    require_equal((RESULTS_ROOT / "post_run_audit.json").exists(), False, "result audit")
    require_equal(
        foundation_paths()["post_run_audit"].exists(), False, "registered audit file"
    )

    print(
        json.dumps(
            {
                "status": "PASS",
                "result_manifest_sha256": manifest_sha256,
                "blind_packet_sha256": artifact_sha256(BLIND_PACKET_PATH),
                "result_file_count": manifest["file_count"],
                "primary_execution_count": manifest["primary_execution_count"],
                "candidate_count": manifest["candidate_count"],
                "experimental_failure_count": manifest[
                    "experimental_failure_count"
                ],
                "audited_answer_count": packet["audited_answer_count"],
                "selected_question_count": len(question_counts),
                "entries_per_question": 9,
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
