"""Dry-run or explicitly execute the frozen Gate 4 held-out schedule.

The default path is offline. Paid calls require a reviewed/publicly recorded
freeze manifest, an explicit --live flag, and an exact authorization phrase.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.gate4_foundation import verify_gate4_foundation  # noqa: E402
from bimchange_agent.gate4_orchestration import (  # noqa: E402
    FREEZE_MANIFEST_PATH,
    REVIEW_STATE_PATH,
    SCHEDULE_PATH,
    artifact_sha256,
    budget_policy,
    foundation_paths,
    load_json,
    load_review_state,
    reproduce_gate3_retained_artifacts,
    stage_frozen_gate3_runtime,
    write_json,
)
from bimchange_agent.gate4_question_verification import (  # noqa: E402
    verify_production_question_artifacts,
)


AUTHORIZATION_PHRASE = "I_AUTHORIZE_GATE4_PAID_CALLS"
RESULTS_DIR = (
    REPOSITORY_ROOT
    / "evals/results/held_out/gate4-controlled-heldout-v0.1.0"
)
CHECKPOINT_PATH = RESULTS_DIR / "checkpoint.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Allow paid API calls")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--authorization-phrase", default="")
    parser.add_argument("--provider-attributed-spend-cny", type=float, default=0.0)
    parser.add_argument("--worker-stage", type=Path, help=argparse.SUPPRESS)
    return parser.parse_args()


def load_local_key() -> None:
    """Load the ignored local key only on the explicitly authorized live path."""
    if os.environ.get("DEEPSEEK_API_KEY"):
        return
    path = REPOSITORY_ROOT / ".env.local"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip() == "DEEPSEEK_API_KEY":
            value = value.strip().strip('"').strip("'")
            if value:
                os.environ["DEEPSEEK_API_KEY"] = value
            return


def verify_preflight() -> dict[str, Any]:
    """Pass protected replay before any held-out artifact is read."""
    foundation = verify_gate4_foundation()
    replay = reproduce_gate3_retained_artifacts()
    held_out = verify_production_question_artifacts()
    return {
        "foundation_guard": foundation["status"],
        "gate3_isolated_replay": replay["status"],
        "held_out_question_verifier": held_out["status"],
        "model_calls_made": 0,
    }


def load_completed_public_freeze() -> dict[str, Any]:
    """Validate the public pre-call state while keeping live authorization absent."""
    review_state = load_review_state()
    if not FREEZE_MANIFEST_PATH.exists():
        raise RuntimeError("Freeze manifest is missing")
    manifest = load_json(FREEZE_MANIFEST_PATH)
    if manifest.get("freeze_status") != "FROZEN_AFTER_USER_REVIEW_AND_PUBLIC_RECORD":
        raise RuntimeError("Freeze manifest has not completed user/public review")
    required = (
        "single_human_pre_run_review",
        "github_issue_3_freeze_record",
        "pull_request_review_and_merge",
    )
    if any(manifest["approval_gates"].get(item) != "COMPLETE" for item in required):
        raise RuntimeError("A required pre-call approval gate is incomplete")
    if manifest["approval_gates"] != review_state["approval_gates"]:
        raise RuntimeError("Freeze manifest and review-state approvals differ")
    if manifest["approval_gates"].get("separate_live_call_authorization") != "PENDING":
        raise RuntimeError("Pre-call manifest must await separate live authorization")
    if manifest.get("live_calls_authorized") is not False:
        raise RuntimeError("Pre-call manifest must keep live calls unauthorized")
    if manifest["review_transition"].get("sha256") != artifact_sha256(
        REVIEW_STATE_PATH
    ):
        raise RuntimeError("Freeze manifest review-state hash mismatch")
    if manifest.get("api_keys_present") or manifest.get("model_outputs_present"):
        raise RuntimeError("Freeze manifest reports forbidden pre-call content")
    return manifest


def require_live_approvals(args: argparse.Namespace) -> dict[str, Any]:
    """Refuse live execution until the exact separate authorization is supplied."""
    if args.authorization_phrase != AUTHORIZATION_PHRASE:
        raise RuntimeError("Exact separate live-call authorization phrase is required")
    manifest = load_completed_public_freeze()
    if args.provider_attributed_spend_cny < 0:
        raise ValueError("Provider-attributed spend cannot be negative")
    if args.provider_attributed_spend_cny >= 25.0:
        raise RuntimeError("CNY 25 hard ceiling already reached")
    status_lines = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    if status_lines:
        results_prefix = RESULTS_DIR.relative_to(REPOSITORY_ROOT).as_posix() + "/"
        changed_paths = [line[3:].replace("\\", "/") for line in status_lines]
        allowed_resume_state = args.resume and all(
            path.startswith(results_prefix) for path in changed_paths
        )
        if not allowed_resume_state:
            raise RuntimeError(
                "Live Gate 4 execution requires a clean reviewed worktree; "
                "resume permits only existing held-out result checkpoints"
            )
    return manifest


class CnyHardCapClient:
    """Add the authoritative CNY ceiling around the frozen provider client."""

    def __init__(self, inner: Any, provider_spend_cny: float) -> None:
        self.inner = inner
        self.ledger = inner.ledger
        self.provider_spend_cny = provider_spend_cny
        self.start_estimated_usd = float(self.ledger.estimated_cost_usd)

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        incremental_usd = max(
            0.0,
            float(self.ledger.estimated_cost_usd) - self.start_estimated_usd,
        )
        projected_incremental_cny = (
            incremental_usd + self.ledger.projected_request_cost(payload)
        ) * 10.0
        if self.provider_spend_cny + projected_incremental_cny >= 25.0:
            raise RuntimeError(
                "Projected provider-attributed spend reaches the CNY 25 hard ceiling"
            )
        return self.inner.create(payload)


def restore_usage(client: Any, usage: dict[str, Any]) -> None:
    """Restore the frozen ledger so the budget spans resumed processes."""
    for field in (
        "request_attempts",
        "successful_responses",
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
    ):
        setattr(client.ledger, field, int(usage.get(field, 0)))
    client.ledger.estimated_cost_usd = float(usage.get("estimated_cost_usd", 0.0))


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    """Replace one checkpoint/result atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    write_json(temporary, value)
    temporary.replace(path)


def load_frozen_runner(stage: Path):
    """Import the copied byte-frozen package under an isolated package name."""
    package_root = stage / "src/bimchange_agent"
    spec = importlib.util.spec_from_file_location(
        "frozen_bimchange_agent",
        package_root / "__init__.py",
        submodule_search_locations=[str(package_root)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load frozen Gate 3 package")
    package = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = package
    spec.loader.exec_module(package)
    return importlib.import_module("frozen_bimchange_agent.gate3_runner")


def run_worker(stage: Path, args: argparse.Namespace) -> None:
    """Execute scheduled primary runs with frozen question-level functions."""
    runner = load_frozen_runner(stage)
    schedule = load_json(SCHEDULE_PATH)
    schedule_sha256 = artifact_sha256(SCHEDULE_PATH)
    policy = budget_policy()
    config = runner.RunConfig(
        budget_usd=policy["automated_estimate"]["runner_budget_usd"]
    )
    provider_client = runner.DeepSeekResponsesClient(config)
    questions_artifact = runner.load_json(runner.QUESTIONS_PATH)
    questions = {
        question["question_id"]: question
        for question in questions_artifact["questions"]
    }
    summary = runner.load_json(runner.MODEL_SUMMARY_PATH)

    completed: list[str] = []
    if args.resume:
        if not CHECKPOINT_PATH.exists():
            raise RuntimeError("--resume requested but no Gate 4 checkpoint exists")
        checkpoint = load_json(CHECKPOINT_PATH)
        if checkpoint["schedule_sha256"] != schedule_sha256:
            raise RuntimeError("Checkpoint schedule hash mismatch")
        if checkpoint["model_config"] != asdict(config):
            raise RuntimeError("Checkpoint model configuration mismatch")
        completed = list(checkpoint["completed_execution_ids"])
        restore_usage(provider_client, checkpoint["usage"])
    elif CHECKPOINT_PATH.exists():
        raise RuntimeError("Existing Gate 4 checkpoint requires --resume")

    client = CnyHardCapClient(provider_client, args.provider_attributed_spend_cny)
    for execution in schedule["executions"]:
        execution_id = execution["execution_id"]
        if execution_id in completed:
            continue
        question = questions[execution["question_id"]]
        workflow = execution["workflow"]
        if workflow == "direct_llm":
            answer, metadata = runner.run_direct_question(
                client, question, questions_artifact["dataset_id"], summary
            )
        else:
            answer, metadata = runner.run_tool_question(
                client,
                workflow,
                question,
                questions_artifact["dataset_id"],
            )
        candidate = {
            "schema_version": "0.1.0",
            "dataset_id": questions_artifact["dataset_id"],
            "question_split": "held_out",
            "workflow": workflow,
            "answers": [answer],
        }
        runner.validate_candidate_schema(candidate)
        primary_dir = RESULTS_DIR / "primary" / execution_id
        atomic_write_json(primary_dir / "candidate.json", candidate)
        usage = client.ledger.public_summary()
        estimated_cny = round(float(usage["estimated_cost_usd"]) * 10.0, 6)
        atomic_write_json(
            primary_dir / "run.json",
            {
                "schema_version": "0.1.0",
                **execution,
                "model_config": asdict(config),
                "frozen_runtime_mapping": {
                    "logical_split": "held_out",
                    "runtime_question_path": "evals/questions/gate3-questions.json",
                    "runtime_change_record_path": "data/ground_truth/gate2-change-records.json",
                    "runtime_direct_input_path": (
                        "evals/inputs/development/gate3-model-pair-summary.json"
                    ),
                },
                "metadata": metadata,
                "cumulative_usage": usage,
                "conservative_estimated_cny": estimated_cny,
            },
        )
        completed.append(execution_id)
        atomic_write_json(
            CHECKPOINT_PATH,
            {
                "schema_version": "0.1.0",
                "schedule_sha256": schedule_sha256,
                "model_config": asdict(config),
                "completed_execution_ids": completed,
                "usage": usage,
                "conservative_estimated_cny": estimated_cny,
                "provider_attributed_spend_cny_at_process_start": (
                    args.provider_attributed_spend_cny
                ),
                "hard_ceiling_cny": 25.0,
            },
        )
        print(
            f"checkpoint {len(completed)}/360 {execution_id}",
            flush=True,
        )

    print(
        json.dumps(
            {
                "status": "PRIMARY_SCHEDULE_COMPLETE",
                "primary_execution_count": len(completed),
                "usage": client.ledger.public_summary(),
                "post_run_audit_generated": False,
            },
            indent=2,
        )
    )


def main() -> None:
    args = parse_args()
    if args.worker_stage is not None:
        require_live_approvals(args)
        load_local_key()
        run_worker(args.worker_stage.resolve(), args)
        return

    preflight = verify_preflight()
    schedule = load_json(SCHEDULE_PATH)
    if not args.live:
        manifest = load_completed_public_freeze()
        with tempfile.TemporaryDirectory(prefix="bimchange-gate4-dry-stage-") as directory:
            staging = stage_frozen_gate3_runtime(Path(directory))
        print(
            json.dumps(
                {
                    "status": "READY_WITHOUT_API_CALL",
                    "preflight": preflight,
                    "schedule_sha256": artifact_sha256(SCHEDULE_PATH),
                    "primary_execution_count": schedule["primary_execution_count"],
                    "repetition_count": schedule["repetition_count"],
                    "workflow_orders": {
                        str(block["repetition"]): block["workflow_order"]
                        for block in schedule["blocks"]
                    },
                    "audit_selection": schedule["audit_selection"],
                    "budget": schedule["budget"],
                    "staged_runtime": staging,
                    "freeze_status": manifest["freeze_status"],
                    "approval_gates": manifest["approval_gates"],
                    "api_call_boundary": "AWAITING_EXACT_SEPARATE_AUTHORIZATION",
                    "live_calls_authorized": False,
                    "model_calls_made": 0,
                },
                indent=2,
            )
        )
        return

    require_live_approvals(args)
    load_local_key()
    with tempfile.TemporaryDirectory(prefix="bimchange-gate4-live-stage-") as directory:
        stage = Path(directory)
        stage_frozen_gate3_runtime(stage)
        worker_args = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker-stage",
            str(stage),
            "--authorization-phrase",
            AUTHORIZATION_PHRASE,
            "--provider-attributed-spend-cny",
            str(args.provider_attributed_spend_cny),
        ]
        if args.resume:
            worker_args.append("--resume")
        subprocess.run(worker_args, cwd=REPOSITORY_ROOT, check=True)


if __name__ == "__main__":
    main()
