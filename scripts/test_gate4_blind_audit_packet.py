"""Offline tamper checks for the Gate 4 blinded audit packet."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable

from generate_gate4_blind_audit_packet import (
    BLIND_PACKET_PATH,
    RESULT_MANIFEST_PATH,
    artifact_sha256,
    build_blind_packet,
    build_result_manifest,
    find_banned_keys,
    load_json,
    require_equal,
)


def expect_failure(action: Callable[[], None], label: str) -> None:
    try:
        action()
    except (KeyError, TypeError, ValueError):
        return
    raise AssertionError(f"Tamper case unexpectedly passed: {label}")


def main() -> None:
    require_equal(load_json(RESULT_MANIFEST_PATH), build_result_manifest(), "manifest")
    packet = load_json(BLIND_PACKET_PATH)
    expected = build_blind_packet(artifact_sha256(RESULT_MANIFEST_PATH))
    require_equal(packet, expected, "packet")
    require_equal(find_banned_keys(packet), [], "packet banned keys")

    mapping_tamper = copy.deepcopy(packet)
    mapping_tamper["entries"][0]["workflow"] = "direct_llm"
    if not find_banned_keys(mapping_tamper):
        raise AssertionError("Workflow mapping tamper was not detected")

    execution_tamper = copy.deepcopy(packet)
    execution_tamper["entries"][0]["execution_id"] = "gate4-primary-001"
    if not find_banned_keys(execution_tamper):
        raise AssertionError("Execution identity tamper was not detected")

    answer_tamper = copy.deepcopy(packet)
    answer_tamper["entries"][0]["candidate_available"] = False
    expect_failure(lambda: require_equal(answer_tamper, expected, "answer"), "answer")

    selection_tamper = copy.deepcopy(packet)
    selection_tamper["entries"].pop()
    expect_failure(
        lambda: require_equal(selection_tamper, expected, "selection"), "selection"
    )

    label_tamper = copy.deepcopy(packet)
    label_tamper["entries"][0]["review"]["review_complete"] = True
    expect_failure(lambda: require_equal(label_tamper, expected, "labels"), "labels")

    manifest_tamper = copy.deepcopy(load_json(RESULT_MANIFEST_PATH))
    manifest_tamper["candidate_count"] += 1
    expect_failure(
        lambda: require_equal(manifest_tamper, build_result_manifest(), "manifest"),
        "manifest",
    )

    print(
        json.dumps(
            {
                "status": "PASS",
                "tamper_cases": 6,
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
