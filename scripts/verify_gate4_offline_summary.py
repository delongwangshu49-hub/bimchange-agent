"""Validate Gate 4 aggregation, audit, and private-review artifacts offline."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from generate_gate4_blind_audit_packet import BLIND_PACKET_PATH, RESULTS_ROOT, require_equal
from generate_gate4_offline_summary import (
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    POST_RUN_AUDIT_PATH,
    PRIVATE_REVIEW_PATH,
    SUMMARY_PATH,
    WORKFLOWS,
    artifact_sha256,
    build_post_run_audit,
    build_private_review_package,
    build_summary,
    load_json,
    write_json,
)
from generate_gate4_scores import SCORES_PATH


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_PATH = RESULTS_ROOT / "gate4-independent-validation.json"
EXPECTED_SUMMARY_SHA256 = (
    "bbcb09c7daf34b83de8e4dd36a7af3abe342bc4c41724b2a6fffa022fedb9694"
)
EXPECTED_POST_RUN_AUDIT_SHA256 = (
    "91c5ccad2f38c62f58049ee142ead927cb1c71aa4d94847ec455d106632b908b"
)
EXPECTED_PRIVATE_REVIEW_SHA256 = (
    "22fe7d3f6b3d5a4dff6e0ca7d9e012e10cd0436a7fdf8ffee2d65fa093e8cf72"
)


def require_close(actual: float, expected: float, label: str) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"{label} mismatch: expected {expected!r}, got {actual!r}")


def independent_manual_counts() -> dict[str, Any]:
    packet = load_json(BLIND_PACKET_PATH)
    claims = [
        claim
        for entry in packet["entries"]
        for claim in entry["review"]["atomic_claims"]
    ]
    labels = Counter(claim["label"] for claim in claims)
    candidates = [entry for entry in packet["entries"] if entry["candidate_available"]]
    return {
        "audited_execution_count": len(packet["entries"]),
        "audited_candidate_count": len(candidates),
        "audited_experimental_failure_count": sum(
            not entry["candidate_available"] for entry in packet["entries"]
        ),
        "atomic_claim_count": len(claims),
        "claim_label_counts": dict(sorted(labels.items())),
        "unsupported_or_indeterminate_claim_rate": (
            labels["unsupported"] + labels["indeterminate"]
        )
        / len(claims),
        "evidence_references_verified_count": sum(
            entry["review"]["evidence_references_verified"] is True
            for entry in candidates
        ),
        "evidence_references_not_verified_count": sum(
            entry["review"]["evidence_references_verified"] is False
            for entry in candidates
        ),
        "safety_overreach_count": sum(
            entry["review"]["safety_overreach"] is True for entry in candidates
        ),
    }


def validate_usage_reconciliation(summary: dict[str, Any]) -> None:
    operations = summary["operations"]
    ledger = operations["evaluation_wide_ledger"]
    accounting = operations["request_accounting"]
    require_equal(
        accounting["retained_logical_response_total"]
        + accounting["additional_successful_responses_in_cumulative_ledger"],
        ledger["successful_responses"],
        "successful response reconciliation",
    )
    require_equal(
        ledger["successful_responses"]
        + accounting["unsuccessful_request_attempt_count"],
        ledger["request_attempts"],
        "request-attempt reconciliation",
    )

    attribution = operations["usage_attribution"]
    require_equal(
        attribution["exactly_attributable_execution_count"]
        + attribution["ambiguous_execution_count"],
        360,
        "usage execution coverage",
    )
    fields = (
        "request_attempts",
        "successful_responses",
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "estimated_cost_usd",
        "conservative_estimated_cny",
    )
    for field in fields:
        exact = sum(
            values.get(field, 0)
            for values in attribution["exact_deltas_by_workflow"].values()
        )
        ambiguous = sum(
            pool["combined_ledger_delta"][field]
            for pool in attribution["ambiguous_pools"]
        )
        expected = ledger[field]
        if isinstance(expected, int):
            require_equal(exact + ambiguous, expected, f"usage {field}")
        else:
            require_close(exact + ambiguous, expected, f"usage {field}")


def build_validation() -> dict[str, Any]:
    require_equal(artifact_sha256(SUMMARY_PATH), EXPECTED_SUMMARY_SHA256, "summary hash")
    require_equal(
        artifact_sha256(POST_RUN_AUDIT_PATH),
        EXPECTED_POST_RUN_AUDIT_SHA256,
        "post-run audit hash",
    )
    require_equal(
        artifact_sha256(PRIVATE_REVIEW_PATH),
        EXPECTED_PRIVATE_REVIEW_SHA256,
        "private review hash",
    )

    summary = load_json(SUMMARY_PATH)
    require_equal(summary, build_summary(), "regenerated summary")
    post_run = load_json(POST_RUN_AUDIT_PATH)
    require_equal(post_run, build_post_run_audit(summary), "regenerated post-run audit")
    private_review = load_json(PRIVATE_REVIEW_PATH)
    require_equal(
        private_review,
        build_private_review_package(summary, post_run),
        "regenerated private review package",
    )

    require_equal(sum(item["execution_count"] for item in summary["overall_by_workflow"].values()), 360, "workflow execution total")
    require_equal(sum(item["candidate_count"] for item in summary["overall_by_workflow"].values()), 348, "workflow candidate total")
    require_equal(set(summary["overall_by_workflow"]), set(WORKFLOWS), "workflows")

    independent_manual = independent_manual_counts()
    reported_manual = summary["manual_audit"]["overall"]
    for field, expected in independent_manual.items():
        actual = reported_manual[field]
        if isinstance(expected, float):
            require_close(actual, expected, f"manual {field}")
        else:
            require_equal(actual, expected, f"manual {field}")

    validate_usage_reconciliation(summary)
    require_equal(summary["uncertainty"]["seed"], BOOTSTRAP_SEED, "bootstrap seed")
    require_equal(
        summary["uncertainty"]["resamples"],
        BOOTSTRAP_RESAMPLES,
        "bootstrap resamples",
    )
    require_equal(
        summary["operations"]["latency"]["aggregate_latency_available"],
        False,
        "latency availability",
    )
    require_equal(summary["uploaded"], False, "summary upload")
    require_equal(summary["public_conclusions_issued"], False, "public conclusions")
    require_equal(post_run["public_release_authorized"], False, "audit release")
    require_equal(private_review["public_release_authorized"], False, "package release")

    return {
        "schema_version": "0.1.0",
        "dataset_id": summary["dataset_id"],
        "status": "PASS_WITH_RECORDED_DATA_LIMITATIONS",
        "validated_artifacts": {
            "scores": {
                "path": SCORES_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": artifact_sha256(SCORES_PATH),
            },
            "summary": {
                "path": SUMMARY_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": artifact_sha256(SUMMARY_PATH),
            },
            "post_run_audit": {
                "path": POST_RUN_AUDIT_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": artifact_sha256(POST_RUN_AUDIT_PATH),
            },
            "private_review_package": {
                "path": PRIVATE_REVIEW_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": artifact_sha256(PRIVATE_REVIEW_PATH),
            },
        },
        "checks": {
            "exact_deterministic_regeneration": True,
            "independent_manual_label_recount": True,
            "execution_and_candidate_grain_reconciliation": True,
            "request_and_usage_ledger_reconciliation": True,
            "bootstrap_seed_and_resample_count_verified": True,
            "limitations_preserved": True,
            "public_release_guards_preserved": True,
        },
        "recorded_data_limitations": [
            "Per-execution latency is unavailable because duration fields were not persisted.",
            "Seven executions occupy three combined usage-attribution pools because four legacy failure rows lack cumulative token/cost metadata.",
            "Per-call-kind token and cost allocation is unavailable from cumulative-only usage records.",
            "Free-text semantics were not deterministically scored; manual audit used one reviewer and cannot support inter-rater agreement.",
        ],
        "private_review_readiness": "READY",
        "public_release_readiness": "NOT_READY_REQUIRES_PRIVATE_REVIEW_DECISION",
        "uploaded": False,
        "model_calls_made": 0,
    }


def main() -> None:
    validation = build_validation()
    write_json(VALIDATION_PATH, validation)
    print(
        json.dumps(
            {
                "status": validation["status"],
                "validation_path": VALIDATION_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
                "validation_sha256": artifact_sha256(VALIDATION_PATH),
                "private_review_readiness": validation["private_review_readiness"],
                "public_release_readiness": validation["public_release_readiness"],
                "uploaded": False,
                "model_calls_made": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
