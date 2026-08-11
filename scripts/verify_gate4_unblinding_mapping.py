"""Independently verify the deterministic Gate 4 unblinding mapping offline."""

from __future__ import annotations

import json

from generate_gate4_unblinding_mapping import (
    BLIND_PACKET_PATH,
    EXPECTED_IMPORTED_PACKET_SHA256,
    MAPPING_PATH,
    artifact_sha256,
    build_mapping,
    load_json,
    require_equal,
)


def main() -> None:
    mapping = load_json(MAPPING_PATH)
    expected = build_mapping()
    require_equal(mapping, expected, "unblinding mapping")
    rows = mapping["entries"]
    require_equal(len({row["audit_code"] for row in rows}), 135, "audit codes")
    require_equal(len({row["execution_id"] for row in rows}), 135, "execution IDs")
    require_equal(
        len(
            {
                (row["question_id"], row["workflow"], row["repetition"])
                for row in rows
            }
        ),
        135,
        "question/workflow/repetition tuples",
    )
    require_equal(
        artifact_sha256(BLIND_PACKET_PATH),
        EXPECTED_IMPORTED_PACKET_SHA256,
        "completed audit packet hash after mapping",
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "mapping_sha256": artifact_sha256(MAPPING_PATH),
                "mapping_row_count": len(rows),
                "unique_execution_count": len(
                    {row["execution_id"] for row in rows}
                ),
                "unique_question_workflow_repetition_count": len(
                    {
                        (row["question_id"], row["workflow"], row["repetition"])
                        for row in rows
                    }
                ),
                "completed_audit_packet_unchanged": True,
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
