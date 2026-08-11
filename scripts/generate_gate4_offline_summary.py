"""Aggregate frozen Gate 4 scores, human audit labels, uncertainty, and operations."""

from __future__ import annotations

import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from generate_gate3_reference_answers import build_canonical_predictions
from generate_gate4_blind_audit_packet import (
    BLIND_PACKET_PATH,
    RESULTS_ROOT,
    require_equal,
)
from generate_gate4_scores import (
    EXPECTED_IMPORTED_PACKET_SHA256,
    EXPECTED_MAPPING_SHA256,
    EXPECTED_REFERENCE_ARTIFACT_SHA256,
    EXPECTED_REFERENCE_RAW_SHA256,
    EXPECTED_RESULT_MANIFEST_SHA256,
    EXPECTED_SCHEDULE_SHA256,
    SCORES_PATH,
    artifact_sha256,
    canonical_hash,
    foundation_paths,
    load_json,
    sha256_file,
    write_json,
)
from generate_gate4_unblinding_mapping import MAPPING_PATH
from verify_gate4_scores import EXPECTED_SCORES_SHA256, fact


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = RESULTS_ROOT / "gate4-offline-summary.json"
PRIVATE_REVIEW_PATH = RESULTS_ROOT / "gate4-private-review-package.json"
POST_RUN_AUDIT_PATH = foundation_paths()["post_run_audit"]
BOOTSTRAP_SEED = 20260808
BOOTSTRAP_RESAMPLES = 2000
WORKFLOWS = ("direct_llm", "tool_using_agent", "proposed")
METRICS = (
    "completion_rate",
    "status_accuracy",
    "semantic_exact_match_accuracy",
    "change_precision",
    "change_recall",
    "change_f1",
    "evidence_support_rate",
)


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def load_analysis_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scores = load_json(SCORES_PATH)
    require_equal(artifact_sha256(SCORES_PATH), EXPECTED_SCORES_SHA256, "scores hash")
    reference_answers = load_json(foundation_paths()["reference_answers"])
    reference = build_canonical_predictions(reference_answers)
    expected = {answer["question_id"]: answer for answer in reference["answers"]}
    rows: list[dict[str, Any]] = []
    for score_row in scores["execution_scores"]:
        execution_id = score_row["execution_id"]
        candidate_path = RESULTS_ROOT / "primary" / execution_id / "candidate.json"
        expected_answer = expected[score_row["question_id"]]
        expected_facts = {fact(item) for item in expected_answer["predictions"]}
        if candidate_path.is_file():
            candidate_answer = load_json(candidate_path)["answers"][0]
            actual_facts = {fact(item) for item in candidate_answer["predictions"]}
            score = score_row["score"]
            prediction_count = len(candidate_answer["predictions"])
            supported_count = round(score["evidence_support_rate"] * prediction_count)
            status_match = int(score["per_question"][0]["status_match"])
            exact_match = int(score["per_question"][0]["exact_match"])
        else:
            actual_facts = set()
            prediction_count = 0
            supported_count = 0
            status_match = 0
            exact_match = 0
        rows.append(
            {
                **{key: score_row[key] for key in (
                    "execution_id", "workflow", "repetition", "question_id", "category"
                )},
                "candidate_available": score_row["candidate_available"],
                "completion": int(score_row["candidate_available"]),
                "status_match": status_match,
                "exact_match": exact_match,
                "true_positive": len(expected_facts & actual_facts),
                "expected_count": len(expected_facts),
                "actual_count": len(actual_facts),
                "evidence_supported_count": supported_count,
                "prediction_count": prediction_count,
            }
        )
    require_equal(len(rows), 360, "analysis row count")
    return rows, scores


def aggregate(rows: Iterable[dict[str, Any]]) -> dict[str, float | int]:
    values = list(rows)
    count = len(values)
    true_positive = sum(row["true_positive"] for row in values)
    expected = sum(row["expected_count"] for row in values)
    actual = sum(row["actual_count"] for row in values)
    precision = true_positive / actual if actual else float(not expected)
    recall = true_positive / expected if expected else float(not actual)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    prediction_count = sum(row["prediction_count"] for row in values)
    supported = sum(row["evidence_supported_count"] for row in values)
    return {
        "execution_count": count,
        "candidate_count": sum(row["completion"] for row in values),
        "completion_rate": sum(row["completion"] for row in values) / count,
        "status_accuracy": sum(row["status_match"] for row in values) / count,
        "semantic_exact_match_accuracy": sum(row["exact_match"] for row in values)
        / count,
        "change_precision": precision,
        "change_recall": recall,
        "change_f1": f1,
        "evidence_support_rate": supported / prediction_count
        if prediction_count
        else 1.0,
    }


def repetition_summary(scores: dict[str, Any]) -> dict[str, Any]:
    groups = {
        (group["workflow"], group["repetition"]): group
        for group in scores["workflow_repetition_scores"]
    }
    result: dict[str, Any] = {}
    for workflow in WORKFLOWS:
        repetitions = [groups[(workflow, repetition)] for repetition in (1, 2, 3)]
        across: dict[str, Any] = {}
        for metric in METRICS:
            values = [item["metrics"][metric] for item in repetitions]
            across[metric] = {
                "mean": statistics.fmean(values),
                "sample_standard_deviation": statistics.stdev(values),
                "minimum": min(values),
                "maximum": max(values),
            }
        result[workflow] = {
            "per_repetition": [
                {
                    "repetition": item["repetition"],
                    "candidate_count": item["candidate_count"],
                    "experimental_failure_count": item[
                        "experimental_failure_count"
                    ],
                    "metrics": {metric: item["metrics"][metric] for metric in METRICS},
                    "status_consistent": item["metrics"]["status_consistent"],
                }
                for item in repetitions
            ],
            "across_repetition_summary": across,
        }
    return result


def category_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    categories = sorted({row["category"] for row in rows})
    return {
        workflow: {
            category: aggregate(
                row
                for row in rows
                if row["workflow"] == workflow and row["category"] == category
            )
            for category in categories
        }
        for workflow in WORKFLOWS
    }


def question_success(rows: list[dict[str, Any]]) -> dict[str, Any]:
    question_ids = sorted({row["question_id"] for row in rows})
    result: dict[str, Any] = {}
    for workflow in WORKFLOWS:
        items = []
        for question_id in question_ids:
            selected = [
                row
                for row in rows
                if row["workflow"] == workflow and row["question_id"] == question_id
            ]
            require_equal(len(selected), 3, "question repetition count")
            items.append(
                {
                    "question_id": question_id,
                    "category": selected[0]["category"],
                    "exact_success_frequency": sum(row["exact_match"] for row in selected),
                    "candidate_frequency": sum(row["completion"] for row in selected),
                }
            )
        result[workflow] = {
            "frequency_distribution": {
                str(value): sum(
                    item["exact_success_frequency"] == value for item in items
                )
                for value in range(4)
            },
            "questions": items,
        }
    return result


def bootstrap(rows: list[dict[str, Any]]) -> dict[str, Any]:
    question_ids = sorted({row["question_id"] for row in rows})
    by_workflow_question: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_workflow_question[(row["workflow"], row["question_id"])].append(row)
    generator = random.Random(BOOTSTRAP_SEED)
    samples = [
        [generator.choice(question_ids) for _ in question_ids]
        for _ in range(BOOTSTRAP_RESAMPLES)
    ]
    pairs = (
        ("direct_llm", "tool_using_agent"),
        ("direct_llm", "proposed"),
        ("tool_using_agent", "proposed"),
    )
    output: dict[str, Any] = {}
    for left, right in pairs:
        point_left = aggregate(row for row in rows if row["workflow"] == left)
        point_right = aggregate(row for row in rows if row["workflow"] == right)
        metric_output: dict[str, Any] = {}
        differences = {metric: [] for metric in METRICS}
        for sample in samples:
            left_rows = [
                row
                for question_id in sample
                for row in by_workflow_question[(left, question_id)]
            ]
            right_rows = [
                row
                for question_id in sample
                for row in by_workflow_question[(right, question_id)]
            ]
            left_metrics = aggregate(left_rows)
            right_metrics = aggregate(right_rows)
            for metric in METRICS:
                differences[metric].append(left_metrics[metric] - right_metrics[metric])
        for metric in METRICS:
            metric_output[metric] = {
                "point_difference_left_minus_right": point_left[metric]
                - point_right[metric],
                "bootstrap_mean_difference": statistics.fmean(differences[metric]),
                "percentile_95_interval": [
                    percentile(differences[metric], 0.025),
                    percentile(differences[metric], 0.975),
                ],
            }
        output[f"{left}_minus_{right}"] = metric_output
    return {
        "method": "question-clustered paired bootstrap; all three repetitions retained within each sampled question cluster",
        "seed": BOOTSTRAP_SEED,
        "resamples": BOOTSTRAP_RESAMPLES,
        "interval": "2.5th to 97.5th percentile",
        "significance_claim_from_interval_alone": False,
        "pairs": output,
    }


def manual_audit_summary() -> dict[str, Any]:
    packet = load_json(BLIND_PACKET_PATH)
    mapping = load_json(MAPPING_PATH)
    require_equal(
        artifact_sha256(BLIND_PACKET_PATH),
        EXPECTED_IMPORTED_PACKET_SHA256,
        "audit packet hash",
    )
    require_equal(artifact_sha256(MAPPING_PATH), EXPECTED_MAPPING_SHA256, "mapping")
    mapped = {row["audit_code"]: row for row in mapping["entries"]}
    joined = []
    for entry in packet["entries"]:
        row = mapped[entry["audit_code"]]
        review = entry["review"]
        joined.append(
            {
                "audit_code": entry["audit_code"],
                "workflow": row["workflow"],
                "repetition": row["repetition"],
                "question_id": row["question_id"],
                "category": row["category"],
                "candidate_available": entry["candidate_available"],
                "claim_labels": [claim["label"] for claim in review["atomic_claims"]],
                "evidence_references_verified": review[
                    "evidence_references_verified"
                ],
                "safety_overreach": review["safety_overreach"],
                "failure_categories": review["failure_categories"],
                "review_complete": review["review_complete"],
            }
        )

    def summarize(values: list[dict[str, Any]]) -> dict[str, Any]:
        labels = [label for row in values for label in row["claim_labels"]]
        label_counts = Counter(labels)
        unsupported_or_indeterminate = label_counts["unsupported"] + label_counts[
            "indeterminate"
        ]
        candidates = [row for row in values if row["candidate_available"]]
        failure_counts = Counter(
            category for row in values for category in row["failure_categories"]
        )
        return {
            "audited_execution_count": len(values),
            "audited_candidate_count": len(candidates),
            "audited_experimental_failure_count": sum(
                not row["candidate_available"] for row in values
            ),
            "atomic_claim_count": len(labels),
            "claim_label_counts": dict(sorted(label_counts.items())),
            "unsupported_or_indeterminate_claim_rate": (
                unsupported_or_indeterminate / len(labels) if labels else 0.0
            ),
            "evidence_references_verified_count": sum(
                row["evidence_references_verified"] is True for row in candidates
            ),
            "evidence_references_not_verified_count": sum(
                row["evidence_references_verified"] is False for row in candidates
            ),
            "safety_overreach_count": sum(
                row["safety_overreach"] is True for row in candidates
            ),
            "failure_category_counts": dict(sorted(failure_counts.items())),
            "all_reviews_complete": all(row["review_complete"] for row in values),
        }

    return {
        "reviewer_count": 1,
        "inter_rater_agreement_claimed": False,
        "selection": {
            "selected_question_count": 15,
            "execution_count": 135,
            "all_five_evidence_boundary_questions_included": True,
            "ten_stratified_additional_questions_included": True,
        },
        "overall": summarize(joined),
        "by_workflow": {
            workflow: summarize([row for row in joined if row["workflow"] == workflow])
            for workflow in WORKFLOWS
        },
        "by_category": {
            category: summarize([row for row in joined if row["category"] == category])
            for category in sorted({row["category"] for row in joined})
        },
    }


def operational_summary() -> dict[str, Any]:
    checkpoint = load_json(RESULTS_ROOT / "checkpoint.json")
    runs = [
        load_json(RESULTS_ROOT / "primary" / f"gate4-primary-{ordinal:03d}" / "run.json")
        for ordinal in range(1, 361)
    ]
    failures = [run for run in runs if run.get("status") == "EXPERIMENTAL_FAILURE"]
    repairs = sum(run.get("metadata", {}).get("repair_count", 0) for run in runs)
    proposed_candidates = sum(
        run["workflow"] == "proposed"
        and (RESULTS_ROOT / "primary" / run["execution_id"] / "candidate.json").is_file()
        for run in runs
    )

    usage_fields = (
        "request_attempts",
        "successful_responses",
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "estimated_cost_usd",
    )
    exact_deltas: dict[str, Counter[str]] = {workflow: Counter() for workflow in WORKFLOWS}
    ambiguous_pools: list[dict[str, Any]] = []
    previous_usage = {field: 0 for field in usage_fields}
    previous_cny = 0.0
    ordinal = 1
    exact_execution_count = 0
    while ordinal <= 360:
        run = runs[ordinal - 1]
        if run.get("cumulative_usage") is not None:
            current = run["cumulative_usage"]
            for field in usage_fields:
                exact_deltas[run["workflow"]][field] += current[field] - previous_usage[field]
            exact_deltas[run["workflow"]]["conservative_estimated_cny"] += (
                run["conservative_estimated_cny"] - previous_cny
            )
            previous_usage = {field: current[field] for field in usage_fields}
            previous_cny = run["conservative_estimated_cny"]
            exact_execution_count += 1
            ordinal += 1
            continue

        start = ordinal
        while ordinal <= 360 and runs[ordinal - 1].get("cumulative_usage") is None:
            ordinal += 1
        if ordinal > 360:
            raise ValueError("Final run lacks cumulative usage")
        anchor = runs[ordinal - 1]
        current = anchor["cumulative_usage"]
        execution_ids = [
            runs[index - 1]["execution_id"] for index in range(start, ordinal + 1)
        ]
        ambiguous_pools.append(
            {
                "execution_ids": execution_ids,
                "workflows": [runs[index - 1]["workflow"] for index in range(start, ordinal + 1)],
                "combined_ledger_delta": {
                    **{
                        field: current[field] - previous_usage[field]
                        for field in usage_fields
                    },
                    "conservative_estimated_cny": anchor[
                        "conservative_estimated_cny"
                    ]
                    - previous_cny,
                },
                "reason": "one or more legacy failure rows lack cumulative token/cost metadata, so the next recorded cumulative delta cannot be split exactly",
            }
        )
        previous_usage = {field: current[field] for field in usage_fields}
        previous_cny = anchor["conservative_estimated_cny"]
        ordinal += 1

    retained_candidate_response_ids = sum(
        len(run.get("metadata", {}).get("response_ids", [])) for run in runs
    )
    persisted_failure_raw_responses = sum(
        len(run.get("raw_provider_responses", [])) for run in runs
    )
    retained_logical_core_responses = 120 + 240 + 240
    retained_proposed_validator_responses = proposed_candidates + repairs
    retained_proposed_repair_responses = repairs
    retained_logical_responses = (
        retained_logical_core_responses
        + retained_proposed_validator_responses
        + retained_proposed_repair_responses
    )
    return {
        "evaluation_wide_ledger": {
            **checkpoint["usage"],
            "conservative_estimated_cny": checkpoint["conservative_estimated_cny"],
            "recorded_final_provider_usage_snapshot_cny": 3.59,
            "authoritative_spend_cny": max(
                checkpoint["conservative_estimated_cny"], 3.59
            ),
            "hard_ceiling_cny": checkpoint["hard_ceiling_cny"],
            "hard_ceiling_reached": False,
        },
        "request_accounting": {
            "retained_logical_core_workflow_responses": retained_logical_core_responses,
            "retained_proposed_validator_responses": retained_proposed_validator_responses,
            "retained_proposed_repair_responses": retained_proposed_repair_responses,
            "retained_logical_response_total": retained_logical_responses,
            "persisted_candidate_response_id_count": retained_candidate_response_ids,
            "persisted_failure_raw_response_count": persisted_failure_raw_responses,
            "additional_successful_responses_in_cumulative_ledger": checkpoint["usage"][
                "successful_responses"
            ]
            - retained_logical_responses,
            "unsuccessful_request_attempt_count": checkpoint["usage"][
                "request_attempts"
            ]
            - checkpoint["usage"]["successful_responses"],
            "note": "Logical response counts are reconstructed from the frozen workflow contract; cumulative-ledger excesses include interrupted/recovery attempts and are not reassigned to final outputs.",
        },
        "usage_attribution": {
            "exactly_attributable_execution_count": exact_execution_count,
            "ambiguous_execution_count": sum(
                len(pool["execution_ids"]) for pool in ambiguous_pools
            ),
            "exact_deltas_by_workflow": {
                workflow: dict(counter) for workflow, counter in exact_deltas.items()
            },
            "ambiguous_pools": ambiguous_pools,
            "per_call_kind_token_and_cost_split_available": False,
            "reason": "run.json persists cumulative usage, not per-request token/cost records; four legacy failures also lack token metadata",
        },
        "repair": {
            "proposed_repair_count": repairs,
            "proposed_repair_rate_per_primary_execution": repairs / 120,
            "proposed_repair_rate_per_persisted_candidate": repairs
            / proposed_candidates,
        },
        "failures": {
            "total": len(failures),
            "by_workflow": dict(sorted(Counter(run["workflow"] for run in failures).items())),
            "by_category": dict(
                sorted(Counter(run["failure"]["category"] for run in failures).items())
            ),
            "retry_allowed_count": sum(run["failure"]["retry_allowed"] for run in failures),
            "retry_performed_count": sum(
                run["failure"]["retry_performed"] for run in failures
            ),
        },
        "latency": {
            "per_execution_latency_record_count": 0,
            "aggregate_latency_available": False,
            "reason": "retained run.json files do not persist request start time, elapsed duration, or per-execution latency; completed_at exists only inside some failure raw responses and cannot produce durations",
            "estimated_values_substituted": False,
        },
    }


def build_summary() -> dict[str, Any]:
    require_equal(
        artifact_sha256(foundation_paths()["reference_answers"]),
        EXPECTED_REFERENCE_ARTIFACT_SHA256,
        "reference hash",
    )
    require_equal(
        sha256_file(foundation_paths()["reference_answers"]),
        EXPECTED_REFERENCE_RAW_SHA256,
        "reference raw hash",
    )
    rows, scores = load_analysis_rows()
    return {
        "schema_version": "0.1.0",
        "dataset_id": "gate4-controlled-heldout-v0.1.0",
        "split": "held_out",
        "status": "OFFLINE_AGGREGATION_COMPLETE_PRIVATE_REVIEW_REQUIRED",
        "lineage": {
            "schedule_sha256": EXPECTED_SCHEDULE_SHA256,
            "result_manifest_sha256": EXPECTED_RESULT_MANIFEST_SHA256,
            "completed_audit_packet_sha256": EXPECTED_IMPORTED_PACKET_SHA256,
            "mapping_sha256": EXPECTED_MAPPING_SHA256,
            "reference_answer_artifact_sha256": EXPECTED_REFERENCE_ARTIFACT_SHA256,
            "reference_answer_raw_sha256": EXPECTED_REFERENCE_RAW_SHA256,
            "scores_sha256": EXPECTED_SCORES_SHA256,
        },
        "overall_by_workflow": {
            workflow: aggregate(row for row in rows if row["workflow"] == workflow)
            for workflow in WORKFLOWS
        },
        "repetition": repetition_summary(scores),
        "per_category": category_summary(rows),
        "question_success_frequency": question_success(rows),
        "uncertainty": bootstrap(rows),
        "manual_audit": manual_audit_summary(),
        "operations": operational_summary(),
        "limitations": [
            "Results are repeated measurements on one independently constructed controlled synthetic held-out fixture, not a universal BIM benchmark.",
            "Only three repetitions, one model provider, and the frozen added/deleted/property_modified change boundary are covered.",
            "Free-text answer semantics are not scored by the deterministic scorer; the preselected single-reviewer manual audit is reported separately.",
            "No inter-rater agreement can be claimed because there was one human reviewer.",
            "Per-execution and per-call-kind latency was not persisted and is unavailable; no estimate is substituted.",
            "Per-call-kind token and cost allocation is unavailable because retained usage is cumulative and four legacy failure rows lack token metadata.",
            "Bootstrap intervals describe clustered resampling uncertainty on this fixture and do not by themselves establish statistical significance or external generalizability.",
        ],
        "publication_status": "HOLD_FOR_INDEPENDENT_VALIDATION_AND_PRIVATE_REVIEW",
        "uploaded": False,
        "public_conclusions_issued": False,
        "model_calls_made": 0,
    }


def build_post_run_audit(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "dataset_id": summary["dataset_id"],
        "audit_stage": "post_run",
        "status": "COMPLETE_WITH_RECORDED_LIMITATIONS",
        "single_human_review": summary["manual_audit"],
        "unblinding": {
            "performed_only_after_all_135_reviews_complete": True,
            "mapping_sha256": EXPECTED_MAPPING_SHA256,
            "completed_audit_packet_sha256": EXPECTED_IMPORTED_PACKET_SHA256,
        },
        "scoring": {
            "frozen_gate3_scorer_used": True,
            "scores_sha256": EXPECTED_SCORES_SHA256,
            "independent_validation_required_before_publication": True,
            "free_text_scored": False,
        },
        "operational_limitations": {
            "latency_available": False,
            "per_call_kind_token_and_cost_split_available": False,
            "details": summary["limitations"],
        },
        "result_summary_sha256": artifact_sha256(SUMMARY_PATH),
        "public_release_authorized": False,
        "uploaded": False,
        "model_calls_made": 0,
    }


def build_private_review_package(
    summary: dict[str, Any], post_run_audit: dict[str, Any]
) -> dict[str, Any]:
    del post_run_audit
    return {
        "schema_version": "0.1.0",
        "dataset_id": summary["dataset_id"],
        "status": "READY_FOR_PRIVATE_REVIEW_NOT_PUBLIC_RELEASE",
        "artifacts": {
            "completed_blind_audit_packet": {
                "path": BLIND_PACKET_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": EXPECTED_IMPORTED_PACKET_SHA256,
            },
            "unblinding_mapping": {
                "path": MAPPING_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": EXPECTED_MAPPING_SHA256,
            },
            "execution_scores": {
                "path": SCORES_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": EXPECTED_SCORES_SHA256,
            },
            "offline_summary": {
                "path": SUMMARY_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": artifact_sha256(SUMMARY_PATH),
            },
            "post_run_audit": {
                "path": POST_RUN_AUDIT_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": artifact_sha256(POST_RUN_AUDIT_PATH),
            },
        },
        "review_focus": [
            "Verify the frozen lineage and independent score recomputation.",
            "Review workflow/repetition, category, and question-frequency summaries.",
            "Review clustered bootstrap implementation and interpretation boundary.",
            "Review single-reviewer manual-audit findings without claiming inter-rater agreement.",
            "Accept or resolve the unavailable latency and per-call-kind cost allocation limitations.",
            "Confirm synthetic-fixture, three-repetition, one-provider, and change-type limitations before any public wording.",
        ],
        "public_release_authorized": False,
        "uploaded": False,
        "model_calls_made": 0,
    }


def main() -> None:
    summary = build_summary()
    write_json(SUMMARY_PATH, summary)
    post_run_audit = build_post_run_audit(summary)
    write_json(POST_RUN_AUDIT_PATH, post_run_audit)
    private_review = build_private_review_package(summary, post_run_audit)
    write_json(PRIVATE_REVIEW_PATH, private_review)
    print(
        json.dumps(
            {
                "status": "PASS",
                "summary_sha256": artifact_sha256(SUMMARY_PATH),
                "post_run_audit_sha256": artifact_sha256(POST_RUN_AUDIT_PATH),
                "private_review_package_sha256": artifact_sha256(PRIVATE_REVIEW_PATH),
                "manual_atomic_claim_count": summary["manual_audit"]["overall"][
                    "atomic_claim_count"
                ],
                "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
                "latency_available": False,
                "public_release_authorized": False,
                "uploaded": False,
                "model_calls_made": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
