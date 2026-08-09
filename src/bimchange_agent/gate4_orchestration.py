"""Offline-first Gate 4 scheduling, staging, and freeze helpers.

This module adds orchestration around the byte-frozen Gate 3 question-level
functions.  It never imports or edits those functions while constructing the
pre-call artifacts.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
from collections import Counter
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FOUNDATION_PATH = REPOSITORY_ROOT / "configs" / "gate4-foundation.json"
DESIGN_SPEC_PATH = REPOSITORY_ROOT / "docs" / "gate4-held-out-design-spec.md"
SCHEDULE_PATH = (
    REPOSITORY_ROOT / "evals" / "schedules" / "held_out" / "gate4-run-schedule.json"
)
PRE_RUN_AUDIT_PATH = (
    REPOSITORY_ROOT / "evals" / "audits" / "held_out" / "gate4-pre-run-audit.json"
)
FREEZE_MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "evals"
    / "manifests"
    / "held_out"
    / "gate4-freeze-manifest.json"
)

DATASET_ID = "gate4-controlled-heldout-v0.1.0"
SCHEDULE_SEED = "gate4-question-order-20260808-v1"
AUDIT_SEED = "gate4-audit-selection-20260808-v1"
WORKFLOW_ORDERS = {
    1: ["direct_llm", "tool_using_agent", "proposed"],
    2: ["tool_using_agent", "proposed", "direct_llm"],
    3: ["proposed", "direct_llm", "tool_using_agent"],
}
NON_BOUNDARY_CATEGORIES = (
    "summary",
    "fact_lookup",
    "filtered_lookup",
    "property_change",
    "negative_control",
)


def load_json(path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON object."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected a JSON object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    """Write deterministic human-readable JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256_bytes(value: bytes) -> str:
    """Return a lowercase SHA-256 digest."""
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of one file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_normalized_text_sha256(path: Path) -> str:
    """Hash generated text after the repository's CRLF-to-LF clean filter."""
    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


def artifact_sha256(path: Path) -> str:
    """Hash text as a Git-normalized artifact and binary IFC files raw."""
    return sha256_file(path) if path.suffix.lower() == ".ifc" else git_normalized_text_sha256(path)


def canonical_hash(value: Any) -> str:
    """Hash one JSON value using a stable compact representation."""
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256_bytes(encoded)


def foundation_paths() -> dict[str, Path]:
    """Resolve registered Gate 4 paths without reading their contents."""
    config = load_json(FOUNDATION_PATH)
    return {
        name: (REPOSITORY_ROOT / relative).resolve()
        for name, relative in config["gate4_paths"].items()
        if name != "results_directory"
    }


def budget_policy() -> dict[str, Any]:
    """Return the CNY-denominated hard budget and conservative stop policy."""
    return {
        "supersedes_provisional_budget": {
            "currency": "USD",
            "amount": 0.75,
            "status": "superseded_before_any_gate4_model_call",
        },
        "hard_ceiling": {"currency": "CNY", "amount": 25.0},
        "billing_unit": "CNY for the evaluation-wide hard ceiling",
        "automated_estimate": {
            "source_currency": "USD",
            "conservative_cny_per_usd": 10.0,
            "token_estimate_sublimit_cny": 22.5,
            "runner_budget_usd": 2.25,
            "contingency_reserve_cny": 2.5,
            "pricing_units": "USD per 1,000,000 text tokens",
            "input_usd_per_million": 0.14,
            "cached_input_usd_per_million": 0.0028,
            "output_usd_per_million": 0.28,
        },
        "included_charges": [
            "all retained primary workflow calls",
            "Proposed validator calls",
            "Proposed controlled repair calls",
            "transient retries, including any provider-charged failed attempt",
        ],
        "authoritative_spend_rule": (
            "Use the greater of provider-attributed CNY debit and the conservative "
            "token estimate. The CNY 2.50 reserve covers reporting lag or charged "
            "attempts without usable token metadata."
        ),
        "pre_request_stop_rule": (
            "Stop before a request if current attributable spend plus the conservative "
            "projection could reach or exceed CNY 25.00, or if the automated estimate "
            "could exceed CNY 22.50."
        ),
        "post_response_stop_rule": (
            "Stop immediately if reported or estimated cumulative spend reaches either "
            "threshold; retain the incomplete block and do not change prompts, questions, "
            "workflow logic, or exclusions."
        ),
        "resume_rule": (
            "Resume only after explicit review, under the identical frozen configuration "
            "and from the last compatible checkpoint."
        ),
    }


def _rank(seed: str, question_id: str) -> str:
    return sha256_bytes(f"{seed}:{question_id}".encode("utf-8"))


def build_audit_selection(questions: list[dict[str, Any]]) -> dict[str, Any]:
    """Preselect all evidence boundaries plus ten stratified question IDs."""
    by_category: dict[str, list[str]] = {}
    for question in questions:
        by_category.setdefault(question["category"], []).append(question["question_id"])

    evidence_boundary = sorted(by_category.get("evidence_boundary", []))
    if len(evidence_boundary) != 5:
        raise ValueError("Expected exactly five evidence_boundary questions")

    stratified: dict[str, list[str]] = {}
    for category in NON_BOUNDARY_CATEGORIES:
        candidates = by_category.get(category, [])
        ranked = sorted(candidates, key=lambda item: (_rank(AUDIT_SEED, item), item))
        if len(ranked) < 2:
            raise ValueError(f"Need at least two questions for audit category {category}")
        stratified[category] = ranked[:2]

    additional = [item for category in NON_BOUNDARY_CATEGORIES for item in stratified[category]]
    selected = evidence_boundary + additional
    return {
        "selection_seed": AUDIT_SEED,
        "evidence_boundary_question_ids": evidence_boundary,
        "stratified_additional_question_ids": stratified,
        "all_selected_question_ids": selected,
        "selected_question_count": 15,
        "executions_per_question": 9,
        "expected_audited_answer_count": 135,
        "selection_sha256": canonical_hash(selected),
        "blinding": {
            "status": "protocol_frozen_before_results",
            "neutral_code_format": "A001 through A135 after retained outputs exist",
            "mapping_visibility": (
                "The workflow/repetition mapping is withheld from the reviewer until "
                "all audit labels are saved."
            ),
            "post_run_artifact_generated": False,
        },
    }


def build_schedule(question_artifact: dict[str, Any]) -> dict[str, Any]:
    """Build the exact deterministic 360-execution primary schedule."""
    if question_artifact.get("dataset_id") != DATASET_ID:
        raise ValueError("Unexpected held-out dataset_id")
    if question_artifact.get("split") != "held_out":
        raise ValueError("Gate 4 questions must use split=held_out")
    questions = question_artifact["questions"]
    if len(questions) != 40:
        raise ValueError("Expected exactly 40 held-out questions")
    ids = [question["question_id"] for question in questions]
    if len(ids) != len(set(ids)):
        raise ValueError("Held-out question IDs must be unique")
    category_by_id = {
        question["question_id"]: question["category"] for question in questions
    }

    executions: list[dict[str, Any]] = []
    blocks = []
    ordinal = 0
    for repetition in (1, 2, 3):
        order = sorted(
            ids,
            key=lambda item: (
                _rank(f"{SCHEDULE_SEED}:repetition-{repetition}", item),
                item,
            ),
        )
        workflow_order = WORKFLOW_ORDERS[repetition]
        block_start = ordinal + 1
        for workflow in workflow_order:
            for position, question_id in enumerate(order, start=1):
                ordinal += 1
                executions.append(
                    {
                        "ordinal": ordinal,
                        "execution_id": f"gate4-primary-{ordinal:03d}",
                        "repetition": repetition,
                        "workflow": workflow,
                        "question_position": position,
                        "question_id": question_id,
                        "category": category_by_id[question_id],
                    }
                )
        blocks.append(
            {
                "repetition": repetition,
                "workflow_order": workflow_order,
                "question_order": order,
                "question_order_sha256": canonical_hash(order),
                "primary_execution_ordinals": [block_start, ordinal],
                "primary_execution_count": 120,
            }
        )

    schedule = {
        "schema_version": "0.1.0",
        "dataset_id": DATASET_ID,
        "split": "held_out",
        "schedule_seed": SCHEDULE_SEED,
        "repetition_count": 3,
        "question_count": 40,
        "workflow_count": 3,
        "primary_execution_count": 360,
        "auxiliary_calls_are_primary_executions": False,
        "blocks": blocks,
        "executions": executions,
        "audit_selection": build_audit_selection(questions),
        "budget": budget_policy(),
        "model_calls_made": 0,
    }
    verify_schedule(schedule, question_artifact)
    return schedule


def verify_schedule(
    schedule: dict[str, Any], question_artifact: dict[str, Any]
) -> dict[str, Any]:
    """Verify schedule counts, rotations, uniqueness, and exact coverage."""
    executions = schedule["executions"]
    if len(executions) != 360:
        raise ValueError("Schedule must contain exactly 360 primary executions")
    if [item["ordinal"] for item in executions] != list(range(1, 361)):
        raise ValueError("Schedule ordinals must be consecutive")
    execution_ids = [item["execution_id"] for item in executions]
    if len(execution_ids) != len(set(execution_ids)):
        raise ValueError("Schedule execution IDs must be unique")
    question_ids = {item["question_id"] for item in question_artifact["questions"]}
    counts = Counter(
        (item["repetition"], item["workflow"], item["question_id"])
        for item in executions
    )
    expected_keys = {
        (repetition, workflow, question_id)
        for repetition in (1, 2, 3)
        for workflow in WORKFLOW_ORDERS[repetition]
        for question_id in question_ids
    }
    if set(counts) != expected_keys or any(value != 1 for value in counts.values()):
        raise ValueError("Every repetition/workflow/question tuple must occur exactly once")
    for block in schedule["blocks"]:
        repetition = block["repetition"]
        if block["workflow_order"] != WORKFLOW_ORDERS[repetition]:
            raise ValueError("Frozen workflow rotation changed")
        if set(block["question_order"]) != question_ids:
            raise ValueError("Each block must contain every question exactly once")
        if block["question_order_sha256"] != canonical_hash(block["question_order"]):
            raise ValueError("Question-order hash mismatch")
    selection = schedule["audit_selection"]
    if selection["selected_question_count"] != 15:
        raise ValueError("Audit selection must contain 15 question IDs")
    if selection["expected_audited_answer_count"] != 135:
        raise ValueError("Audit selection must cover 135 answers")
    if len(set(selection["all_selected_question_ids"])) != 15:
        raise ValueError("Audit question selection contains duplicates")
    return {
        "status": "PASS",
        "primary_execution_count": 360,
        "repetition_count": 3,
        "question_count": 40,
        "audit_question_count": 15,
        "expected_audited_answer_count": 135,
        "model_calls_made": 0,
    }


def reproduce_gate3_retained_artifacts() -> dict[str, Any]:
    """Rebuild protected Gate 3 artifacts in an isolated Git archive."""
    from .gate4_foundation import verify_gate4_foundation

    verify_gate4_foundation()
    foundation = load_json(FOUNDATION_PATH)
    expected = {
        item["path"]: item["sha256"] for item in foundation["protected_gate3_files"]
    }
    compared = (
        "evals/reference_answers/gate3-reference-answers.json",
        "evals/reference_answers/gate3-canonical-predictions.json",
        "evals/inputs/development/gate3-model-pair-summary.json",
        "evals/results/development/summary.json",
    )
    archive = subprocess.run(
        ["git", "archive", "--format=tar", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    import tempfile

    with tempfile.TemporaryDirectory(prefix="bimchange-gate3-replay-") as directory:
        root = Path(directory)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
            bundle.extractall(root, filter="data")
        # `git archive` honors checkout EOL conversion on this Windows setup.
        # Restore the guard-verified working-tree byte views inside the isolated
        # snapshot.  This reproduces the historical nested hashes: the question
        # file is LF while the Gate 2 Change Record checkout is CRLF, even though
        # both clean to their exact frozen Git blobs.
        for entry in foundation["protected_gate3_files"]:
            target = root / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((REPOSITORY_ROOT / entry["path"]).read_bytes())
        scripts = (
            "scripts/generate_gate3_reference_answers.py",
            "scripts/generate_gate3_direct_input.py",
            "scripts/test_gate3_scoring.py",
            "scripts/test_change_query.py",
            "scripts/test_gate3_candidate_contract.py",
            "scripts/test_gate3_workflows.py",
            "scripts/summarize_gate3_results.py",
        )
        for script in scripts:
            subprocess.run(
                [sys.executable, script],
                cwd=root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        reproduced = {
            path: git_normalized_text_sha256(root / path) for path in compared
        }
    mismatches = {
        path: {"expected": expected[path], "actual": digest}
        for path, digest in reproduced.items()
        if digest != expected[path]
    }
    if mismatches:
        raise ValueError(f"Gate 3 retained artifact replay mismatch: {mismatches}")
    return {
        "status": "PASS",
        "isolated_git_archive": True,
        "compared_artifact_sha256": reproduced,
        "positive_and_negative_contract_tests_passed": True,
        "dry_run_passed": True,
        "model_calls_made": 0,
    }


def stage_frozen_gate3_runtime(destination: Path) -> dict[str, Any]:
    """Map held-out artifacts to frozen Gate 3 runtime paths in isolation."""
    destination = destination.resolve()
    paths = foundation_paths()
    package_source = REPOSITORY_ROOT / "src" / "bimchange_agent"
    package_target = destination / "src" / "bimchange_agent"
    package_target.mkdir(parents=True, exist_ok=True)
    frozen_modules = (
        "__init__.py",
        "gate3_runner.py",
        "change_query.py",
        "evidence_validation.py",
    )
    for name in frozen_modules:
        shutil.copyfile(package_source / name, package_target / name)
    shutil.copytree(REPOSITORY_ROOT / "schemas", destination / "schemas")

    mappings = {
        paths["questions"]: destination / "evals/questions/gate3-questions.json",
        paths["direct_input"]: (
            destination / "evals/inputs/development/gate3-model-pair-summary.json"
        ),
        paths["change_records"]: (
            destination / "data/ground_truth/gate2-change-records.json"
        ),
    }
    for source, target in mappings.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    if (destination / "evals/reference_answers").exists():
        raise RuntimeError("Reference answers must not enter the staged runtime")
    return {
        "status": "PASS",
        "staged_root": str(destination),
        "frozen_module_count": len(frozen_modules),
        "mapped_held_out_input_count": len(mappings),
        "reference_answers_staged": False,
        "model_calls_made": 0,
    }


def build_pre_run_audit(
    question_artifact: dict[str, Any],
    change_artifact: dict[str, Any],
    schedule: dict[str, Any],
    automated_reports: dict[str, Any],
) -> dict[str, Any]:
    """Build the machine-complete audit plus a truthful human-review gate."""
    reference_status = {
        answer["question_id"]: answer["status"]
        for answer in load_json(foundation_paths()["reference_answers"])["answers"]
    }
    record_rows = [
        {
            "change_id": record["change_id"],
            "global_id": record["global_id"],
            "change_type": record["change_type"],
            "entity_type": record["entity_type"],
            "building_storey": record["location"]["building_storey"]["name"],
            "automated_evidence_check": "PASS",
            "human_check": "PENDING_USER_REVIEW",
        }
        for record in change_artifact["changes"]
    ]
    question_rows = [
        {
            "question_id": question["question_id"],
            "category": question["category"],
            "expected_status": reference_status[question["question_id"]],
            "automated_alignment_check": "PASS",
            "human_check": "PENDING_USER_REVIEW",
        }
        for question in question_artifact["questions"]
    ]
    return {
        "schema_version": "0.1.0",
        "dataset_id": DATASET_ID,
        "audit_stage": "pre_run",
        "status": "READY_FOR_SINGLE_HUMAN_REVIEW",
        "automated_review": {
            "status": "PASS",
            "reports": automated_reports,
            "change_record_count": len(record_rows),
            "question_count": len(question_rows),
            "schedule_sha256": artifact_sha256(SCHEDULE_PATH),
        },
        "human_review": {
            "reviewer_count": 1,
            "status": "PENDING_USER_REVIEW",
            "inter_rater_agreement_claimed": False,
            "checklist": {
                "ifc_evidence": "PENDING",
                "location_support": "PENDING",
                "old_new_values": "PENDING",
                "question_selection_alignment": "PENDING",
                "answerability": "PENDING",
                "wording_independence": "PENDING",
                "safety_boundaries": "PENDING",
                "licensing": "PENDING",
                "personal_or_sensitive_information_absent": "PENDING",
            },
            "records": record_rows,
            "questions": question_rows,
        },
        "post_run_manual_audit": schedule["audit_selection"],
        "failure_categories": [
            "question_understanding",
            "tool_selection",
            "parameter_generation",
            "ifc_query_or_diff_tool",
            "data_normalization",
            "explanation",
            "evidence_citation",
            "validator_false_negative_or_positive",
            "schema_or_output_format",
            "safety_overreach",
            "data_does_not_support_answer",
            "infrastructure_transient_failure",
        ],
        "model_calls_made": 0,
        "model_outputs_present": False,
        "post_run_artifacts_generated": False,
    }


def build_freeze_manifest(
    implementation_commit: str,
    verification: dict[str, Any],
) -> dict[str, Any]:
    """Build a complete pre-call manifest tied to the implementation commit."""
    foundation = load_json(FOUNDATION_PATH)
    paths = foundation_paths()
    artifacts = {
        "design_spec": DESIGN_SPEC_PATH,
        "source_ifc": paths["source_ifc"],
        "revised_ifc": paths["revised_ifc"],
        "operation_ledger": paths["operation_ledger"],
        "change_records": paths["change_records"],
        "questions": paths["questions"],
        "reference_answers": paths["reference_answers"],
        "direct_input": paths["direct_input"],
        "run_schedule": SCHEDULE_PATH,
        "pre_run_audit": PRE_RUN_AUDIT_PATH,
    }
    return {
        "schema_version": "0.1.0",
        "dataset_id": DATASET_ID,
        "freeze_stage": "pre_call",
        "freeze_status": "AWAITING_USER_REVIEW_AND_PUBLIC_RECORD",
        "gate3_baseline_commit": foundation["gate3_baseline_commit"],
        "gate4_public_input_baseline_commit": (
            "9022ce7c912273bf2442ac42df490f49477ba751"
        ),
        "gate4_implementation_commit": implementation_commit,
        "design_spec_review_status": "frozen_2026-08-08",
        "artifacts": {
            name: {
                "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": artifact_sha256(path),
            }
            for name, path in artifacts.items()
        },
        "protected_gate3_files": foundation["protected_gate3_files"],
        "model_configuration": {
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "reasoning_effort": "high",
            "max_output_tokens": 16000,
            "store": False,
            "max_transient_retries": 2,
            "direct_answer_repairs": 0,
            "tool_using_answer_repairs": 0,
            "proposed_max_controlled_repairs": 1,
        },
        "run_configuration": {
            "repetitions": 3,
            "primary_execution_count": 360,
            "workflow_orders": WORKFLOW_ORDERS,
            "schedule_sha256": artifact_sha256(SCHEDULE_PATH),
            "audit_selection_sha256": load_json(SCHEDULE_PATH)["audit_selection"][
                "selection_sha256"
            ],
            "budget": budget_policy(),
        },
        "offline_verification": verification,
        "approval_gates": {
            "single_human_pre_run_review": "PENDING",
            "github_issue_3_freeze_record": "PENDING",
            "pull_request_review_and_merge": "PENDING",
            "separate_live_call_authorization": "PENDING",
        },
        "api_keys_present": False,
        "model_outputs_present": False,
        "post_run_audit_present": False,
        "post_run_results_generated": False,
        "model_calls_made": 0,
        "live_calls_authorized": False,
    }
