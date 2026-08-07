"""Plan or run the three Gate 3 development workflows."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.gate3_runner import (  # noqa: E402
    DeepSeekResponsesClient,
    QUESTIONS_PATH,
    RunConfig,
    dry_run_plan,
    load_json,
    run_workflow,
    validate_candidate_schema,
)


RESULTS_DIR = REPOSITORY_ROOT / "evals" / "results" / "development"


def load_local_key() -> None:
    """Load DEEPSEEK_API_KEY from ignored .env.local only when needed."""
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


def write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workflow",
        choices=["all", "direct_llm", "tool_using_agent", "proposed"],
        default="all",
    )
    parser.add_argument("--live", action="store_true", help="Allow paid API calls")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume compatible per-question checkpoints",
    )
    parser.add_argument("--budget-usd", type=float, default=0.5)
    parser.add_argument("--question-id", action="append", default=[])
    return parser.parse_args()


def restore_usage(client: DeepSeekResponsesClient, usage: dict[str, object]) -> None:
    """Restore a safe checkpoint ledger so the hard budget spans resumed runs."""
    for field in (
        "request_attempts",
        "successful_responses",
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
    ):
        setattr(client.ledger, field, int(usage.get(field, 0)))
    client.ledger.estimated_cost_usd = float(usage.get("estimated_cost_usd", 0.0))


def load_checkpoint(
    candidate_path: Path,
    metadata_path: Path,
    workflow: str,
    config: RunConfig,
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]], dict[str, object]]:
    """Load a compatible partial run without mixing model configurations."""
    if not candidate_path.exists() and not metadata_path.exists():
        return {}, {}, {}
    if not candidate_path.exists() or not metadata_path.exists():
        raise RuntimeError(f"Incomplete checkpoint pair for {workflow}")
    candidate = load_json(candidate_path)
    metadata = load_json(metadata_path)
    validate_candidate_schema(candidate)
    if candidate["workflow"] != workflow or metadata.get("workflow") != workflow:
        raise RuntimeError(f"Checkpoint workflow mismatch for {workflow}")
    if metadata.get("model_config") != asdict(config):
        raise RuntimeError(
            f"Checkpoint model configuration mismatch for {workflow}; archive it first"
        )
    answers = {answer["question_id"]: answer for answer in candidate["answers"]}
    questions = {
        item["question_id"]: item for item in metadata.get("questions", [])
    }
    if set(answers) != set(questions):
        raise RuntimeError(f"Checkpoint answer/metadata mismatch for {workflow}")
    return answers, questions, metadata.get("usage") or {}


def run_checkpointed_workflow(
    client: DeepSeekResponsesClient,
    config: RunConfig,
    workflow: str,
    selected_ids: set[str] | None,
    *,
    resume: bool,
) -> list[str]:
    """Run and persist one question at a time so long jobs can resume safely."""
    candidate_path = RESULTS_DIR / f"{workflow}.json"
    metadata_path = RESULTS_DIR / f"{workflow}.run.json"
    if resume:
        answers, question_metadata, prior_usage = load_checkpoint(
            candidate_path, metadata_path, workflow, config
        )
        restore_usage(client, prior_usage)
    else:
        answers, question_metadata = {}, {}

    questions_artifact = load_json(QUESTIONS_PATH)
    question_ids = [
        question["question_id"]
        for question in questions_artifact["questions"]
        if selected_ids is None or question["question_id"] in selected_ids
    ]
    if not question_ids:
        raise ValueError("No matching development questions")

    for question_id in question_ids:
        if question_id in answers:
            continue
        run = run_workflow(client, workflow, question_ids={question_id})
        answer = run.candidate["answers"][0]
        answers[question_id] = answer
        question_metadata[question_id] = run.metadata["questions"][0]
        ordered_ids = [item for item in question_ids if item in answers]
        candidate = {
            "schema_version": "0.1.0",
            "dataset_id": questions_artifact["dataset_id"],
            "question_split": "development",
            "workflow": workflow,
            "answers": [answers[item] for item in ordered_ids],
        }
        validate_candidate_schema(candidate)
        write_json(candidate_path, candidate)
        write_json(
            metadata_path,
            {
                "schema_version": "0.1.0",
                "workflow": workflow,
                "model_config": asdict(config),
                "usage": client.ledger.public_summary(),
                "questions": [question_metadata[item] for item in ordered_ids],
            },
        )
        print(
            f"checkpoint {workflow} {len(ordered_ids)}/{len(question_ids)}",
            flush=True,
        )
    return [
        candidate_path.relative_to(REPOSITORY_ROOT).as_posix(),
        metadata_path.relative_to(REPOSITORY_ROOT).as_posix(),
    ]


def main() -> None:
    args = parse_args()
    config = RunConfig(budget_usd=args.budget_usd)
    if not args.live:
        print(json.dumps(dry_run_plan(config), indent=2))
        return

    load_local_key()
    client = DeepSeekResponsesClient(config)
    workflows = (
        ["direct_llm", "tool_using_agent", "proposed"]
        if args.workflow == "all"
        else [args.workflow]
    )
    question_ids = set(args.question_id) or None
    written = []
    for workflow in workflows:
        written.extend(
            run_checkpointed_workflow(
                client,
                config,
                workflow,
                question_ids,
                resume=args.resume,
            )
        )
    print(
        json.dumps(
            {
                "status": "COMPLETE",
                "written": written,
                "usage": client.ledger.public_summary(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
