"""Build a machine-readable summary of the final Gate 3 development runs."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.evidence_validation import load_json  # noqa: E402
from score_gate3_predictions import REFERENCE_PATH, score_candidate  # noqa: E402


RESULTS_DIR = REPOSITORY_ROOT / "evals" / "results" / "development"
SUMMARY_PATH = RESULTS_DIR / "summary.json"
WORKFLOWS = ("direct_llm", "tool_using_agent", "proposed")


def main() -> None:
    reference = load_json(REFERENCE_PATH)
    results = {}
    total_cost = 0.0
    common_model_config = None
    for workflow in WORKFLOWS:
        candidate = load_json(RESULTS_DIR / f"{workflow}.json")
        metadata = load_json(RESULTS_DIR / f"{workflow}.run.json")
        metrics = score_candidate(reference, candidate)
        usage = metadata["usage"]
        total_cost += float(usage["estimated_cost_usd"])
        comparable_config = {
            key: value
            for key, value in metadata["model_config"].items()
            if key != "budget_usd"
        }
        if common_model_config is None:
            common_model_config = comparable_config
        elif common_model_config != comparable_config:
            raise ValueError("Final workflows do not share one model configuration")

        questions = metadata.get("questions", [])
        result = {
            "metrics": metrics,
            "usage": usage,
            "repair_count": sum(int(item.get("repair_count", 0)) for item in questions),
        }
        if workflow == "proposed":
            result["final_claim_pass_count"] = sum(
                item["final_claim_validation"]["overall_verdict"] == "pass"
                for item in questions
            )
            result["final_tool_coverage_complete_count"] = sum(
                bool(item["final_tool_coverage_validation"]["complete"])
                for item in questions
            )
        results[workflow] = result

    summary = {
        "schema_version": "0.1.0",
        "dataset_id": reference["dataset_id"],
        "question_split": "development",
        "question_count": len(reference["answers"]),
        "model_config": common_model_config,
        "results": results,
        "recorded_final_run_estimated_cost_usd": round(total_cost, 6),
        "caveats": [
            "These are development-set results produced after iterative prompt and contract debugging.",
            "They are not held-out results and must not be presented as a general benchmark.",
            "Each final question-condition pair has one retained answer; no variance estimate is available.",
            "The Proposed claim validator uses the same model provider and is not human ground truth.",
            "Discarded diagnostic attempts are excluded from the recorded final-run cost.",
        ],
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
