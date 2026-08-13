"""Verify the frozen N=1 design-diagnostic protocol without executing it."""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from pathlib import Path

from bimchange_agent.product_core import (
    CHANGE_RECORD_FILE_NAME,
    RAW_DIFF_FILE_NAME,
    diff_ifc_pair,
)

from .acceptance import DEFAULT_REVISED, DEFAULT_SOURCE
from .traceability import (
    MANIFEST_FILE_NAME,
    generate_trace_manifest,
    sha256_file,
    strict_load_json,
    verify_trace_manifest,
    write_json,
)


ROOT = Path(__file__).resolve().parent
PROTOCOL_PATH = ROOT / "n1-review-protocol.json"
LOG_TEMPLATE_PATH = ROOT / "n1-review-log.template.json"


def verify_n1_protocol() -> dict[str, object]:
    protocol = strict_load_json(PROTOCOL_PATH)
    template = strict_load_json(LOG_TEMPLATE_PATH)
    assert protocol["protocol_id"] == "r1-n1-review-diagnostic-0.1.0"
    assert protocol["status"] == "FROZEN_BEFORE_EXECUTION"
    assert protocol["execution_status"] == "NOT_STARTED"
    assert protocol["participant"] == {
        "count": 1,
        "role": "sole_developer",
        "prior_knowledge": "author_of_data_and_implementation",
        "claim_boundary": "design_diagnostic_only",
    }
    assert protocol["input_scope"]["controlled_repository_fixture_only"] is True
    assert protocol["input_scope"]["external_ifc_files"] is False
    assert protocol["input_scope"]["model_calls_made"] == 0
    schedule = protocol["schedule"]
    assert len(schedule) == 8
    assert [item["trial_id"] for item in schedule] == [
        f"N1-T{index:02d}" for index in range(1, 9)
    ]
    assert len({item["task_type"] for item in schedule}) == len(schedule)
    assert Counter(item["condition"] for item in schedule) == {"A": 4, "B": 4}
    assert "user_benefit_claim" in protocol["analysis"]["forbidden"]
    assert "pseudo_replication" in protocol["analysis"]["forbidden"]
    assert template["protocol_id"] == protocol["protocol_id"]
    assert template["session_status"] == "NOT_STARTED"
    assert template["schedule_expected_trial_count"] == len(schedule)
    assert template["trials"] == []
    assert template["model_calls_made"] == 0

    with tempfile.TemporaryDirectory(prefix="bimchange-r1-n1-verify-") as directory:
        output = Path(directory)
        diff_ifc_pair(DEFAULT_SOURCE, DEFAULT_REVISED, output)
        records_path = output / CHANGE_RECORD_FILE_NAME
        raw_path = output / RAW_DIFF_FILE_NAME
        manifest_path = output / MANIFEST_FILE_NAME
        manifest = generate_trace_manifest(
            DEFAULT_SOURCE,
            DEFAULT_REVISED,
            records_path,
            raw_path,
        )
        write_json(manifest_path, manifest)
        verification = verify_trace_manifest(
            manifest_path,
            DEFAULT_SOURCE,
            DEFAULT_REVISED,
            records_path,
            raw_path,
        )
        assert verification["status"] == "PASS"
        actual_hashes = {
            CHANGE_RECORD_FILE_NAME: sha256_file(records_path),
            RAW_DIFF_FILE_NAME: sha256_file(raw_path),
            MANIFEST_FILE_NAME: sha256_file(manifest_path),
        }
    assert actual_hashes == protocol["frozen_artifacts"]
    return {
        "status": "PASS",
        "protocol_id": protocol["protocol_id"],
        "trial_count": len(schedule),
        "condition_counts": dict(
            sorted(Counter(item["condition"] for item in schedule).items())
        ),
        "frozen_artifacts_match": True,
        "execution_status": protocol["execution_status"],
        "external_ifc_files_accessed": False,
        "model_calls_made": 0,
    }


def main() -> int:
    print(json.dumps(verify_n1_protocol(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
