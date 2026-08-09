"""Verify the paused Gate 4 runtime amendment without model calls."""

from __future__ import annotations

import argparse
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
    FREEZE_MANIFEST_PATH,
    PRE_RUN_AUDIT_PATH,
    REVIEW_STATE_PATH,
    SCHEDULE_PATH,
    artifact_sha256,
    foundation_paths,
    load_json,
)


AMENDMENT_PATH = REPOSITORY_ROOT / "configs/gate4-runtime-amendment.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--implementation-only",
        action="store_true",
        help="Skip verification of ignored local checkpoint and result files",
    )
    return parser.parse_args()


def require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def verify_implementation(amendment: dict[str, Any]) -> dict[str, Any]:
    for label, item in amendment["implementation_artifacts"].items():
        path = REPOSITORY_ROOT / item["path"]
        if not path.is_file():
            raise FileNotFoundError(f"Missing amendment artifact {label}: {path}")
        require_equal(artifact_sha256(path), item["sha256"], f"{label} SHA-256")

    frozen = amendment["frozen_hashes_unchanged"]
    require_equal(artifact_sha256(SCHEDULE_PATH), frozen["schedule"], "schedule hash")
    schedule = load_json(SCHEDULE_PATH)
    require_equal(
        schedule["audit_selection"]["selection_sha256"],
        frozen["audit_selection"],
        "audit selection hash",
    )
    require_equal(
        artifact_sha256(PRE_RUN_AUDIT_PATH),
        frozen["completed_pre_run_audit"],
        "pre-run audit hash",
    )
    require_equal(
        artifact_sha256(REVIEW_STATE_PATH),
        frozen["review_state"],
        "review-state hash",
    )
    require_equal(
        artifact_sha256(FREEZE_MANIFEST_PATH),
        frozen["final_freeze_manifest"],
        "freeze-manifest hash",
    )
    require_equal(amendment["live_calls_authorized"], False, "live authorization")
    require_equal(amendment["paid_calls_paused"], True, "paid-call pause")
    return {
        "implementation_artifact_count": len(amendment["implementation_artifacts"]),
        "frozen_hash_count": len(frozen),
    }


def verify_local_recovery(amendment: dict[str, Any]) -> dict[str, Any]:
    state = amendment["local_recovery_state"]
    checkpoint_item = state["checkpoint"]
    checkpoint_path = REPOSITORY_ROOT / checkpoint_item["path"]
    require_equal(
        artifact_sha256(checkpoint_path),
        checkpoint_item["sha256"],
        "local checkpoint hash",
    )
    checkpoint = load_json(checkpoint_path)
    trigger = amendment["trigger"]
    completed = checkpoint["completed_execution_ids"]
    expected_completed = [
        f"gate4-primary-{number:03d}"
        for number in range(1, trigger["paid_execution_paused_after_ordinal"] + 1)
    ]
    require_equal(completed, expected_completed, "completed execution sequence")
    require_equal(
        checkpoint["usage"]["request_attempts"],
        amendment["runtime_accounting"]["checkpointed_request_attempts"],
        "checkpoint request attempts",
    )
    require_equal(
        checkpoint["usage"]["successful_responses"],
        amendment["runtime_accounting"]["checkpointed_successful_responses"],
        "checkpoint successful responses",
    )
    require_equal(
        checkpoint["conservative_estimated_cny"],
        amendment["runtime_accounting"]["checkpointed_conservative_estimated_cny"],
        "checkpoint conservative CNY",
    )

    results_dir = checkpoint_path.parent / "primary"
    failure_ids: list[str] = []
    candidate_count = 0
    for execution_id in completed:
        execution_dir = results_dir / execution_id
        run_path = execution_dir / "run.json"
        if not run_path.is_file():
            raise FileNotFoundError(f"Missing run record: {run_path}")
        run = load_json(run_path)
        candidate_path = execution_dir / "candidate.json"
        if run.get("status") == "EXPERIMENTAL_FAILURE":
            failure_ids.append(execution_id)
            require_equal(candidate_path.exists(), False, f"{execution_id} candidate")
            require_equal(
                run["failure"]["retry_performed"], False, f"{execution_id} retry"
            )
        else:
            if not candidate_path.is_file():
                raise FileNotFoundError(f"Missing candidate: {candidate_path}")
            candidate_count += 1

    require_equal(
        failure_ids,
        trigger["experimental_failure_execution_ids"],
        "experimental failure IDs",
    )
    require_equal(candidate_count, trigger["retained_candidate_count"], "candidate count")
    for execution_id, expected_hash in state["manual_failure_record_sha256"].items():
        path = results_dir / execution_id / "run.json"
        require_equal(
            artifact_sha256(path), expected_hash, f"{execution_id} failure-record hash"
        )

    post_run_audit = foundation_paths()["post_run_audit"]
    require_equal(post_run_audit.exists(), False, "post-run audit absence")
    return {
        "completed_execution_count": len(completed),
        "candidate_count": candidate_count,
        "experimental_failure_count": len(failure_ids),
        "post_run_audit_present": False,
    }


def main() -> None:
    args = parse_args()
    foundation = verify_gate4_foundation()
    amendment = load_json(AMENDMENT_PATH)
    implementation = verify_implementation(amendment)
    local = None if args.implementation_only else verify_local_recovery(amendment)
    print(
        json.dumps(
            {
                "status": "PASS",
                "amendment_status": amendment["status"],
                "foundation_status": foundation["status"],
                "implementation": implementation,
                "local_recovery": local,
                "implementation_only": args.implementation_only,
                "live_calls_authorized": False,
                "paid_calls_paused": True,
                "model_calls_made": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
