"""Generate the bilingual Gate 4 held-out results draft from validated JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = (
    REPOSITORY_ROOT
    / "evals/results/held_out/gate4-controlled-heldout-v0.1.0"
)
SUMMARY_PATH = RESULTS_ROOT / "gate4-offline-summary.json"
VALIDATION_PATH = RESULTS_ROOT / "gate4-independent-validation.json"
OUTPUT_PATH = REPOSITORY_ROOT / "docs/gate4-held-out-results.md"
EXPECTED_SUMMARY_SHA256 = (
    "bbcb09c7daf34b83de8e4dd36a7af3abe342bc4c41724b2a6fffa022fedb9694"
)
EXPECTED_VALIDATION_SHA256 = (
    "065fff1ada1d68aa940fee032c28985987bf2a53eb6912a16d8afc189398ab0d"
)
WORKFLOWS = ("direct_llm", "tool_using_agent", "proposed")
WORKFLOW_NAMES = {
    "direct_llm": "Direct LLM",
    "tool_using_agent": "Tool-Using Agent",
    "proposed": "Proposed",
}
METRIC_NAMES = {
    "completion_rate": "Completion rate / 完成率",
    "status_accuracy": "Status accuracy / 状态准确率",
    "semantic_exact_match_accuracy": "Semantic exact match / 语义精确匹配",
    "change_precision": "Change precision / 变更精确率",
    "change_recall": "Change recall / 变更召回率",
    "change_f1": "Change F1 / 变更 F1",
    "evidence_support_rate": "Deterministic evidence support / 确定性证据支持率",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def pp(value: float) -> str:
    return f"{value * 100:+.2f} pp"


def table(headers: list[str], rows: list[list[str]]) -> str:
    rendered = ["| " + " | ".join(headers) + " |"]
    rendered.append("|" + "|".join("---" for _ in headers) + "|")
    rendered.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(rendered)


def overall_table(summary: dict[str, Any]) -> str:
    rows = []
    for workflow in WORKFLOWS:
        metrics = summary["overall_by_workflow"][workflow]
        rows.append(
            [
                WORKFLOW_NAMES[workflow],
                f"{metrics['candidate_count']}/{metrics['execution_count']}",
                pct(metrics["completion_rate"]),
                pct(metrics["status_accuracy"]),
                pct(metrics["semantic_exact_match_accuracy"]),
                pct(metrics["change_precision"]),
                pct(metrics["change_recall"]),
                pct(metrics["change_f1"]),
                pct(metrics["evidence_support_rate"]),
            ]
        )
    return table(
        [
            "Workflow / 工作流",
            "Candidates / 候选",
            "Completion / 完成率",
            "Status / 状态",
            "Exact / 精确匹配",
            "Precision / 精确率",
            "Recall / 召回率",
            "F1",
            "Evidence / 证据",
        ],
        rows,
    )


def repetition_table(summary: dict[str, Any]) -> str:
    rows = []
    for workflow in WORKFLOWS:
        for item in summary["repetition"][workflow]["per_repetition"]:
            metrics = item["metrics"]
            rows.append(
                [
                    WORKFLOW_NAMES[workflow],
                    str(item["repetition"]),
                    f"{item['candidate_count']}/40",
                    pct(metrics["status_accuracy"]),
                    pct(metrics["semantic_exact_match_accuracy"]),
                    pct(metrics["change_precision"]),
                    pct(metrics["change_recall"]),
                    pct(metrics["change_f1"]),
                    pct(metrics["evidence_support_rate"]),
                ]
            )
    return table(
        [
            "Workflow / 工作流",
            "Rep / 重复",
            "Candidates / 候选",
            "Status / 状态",
            "Exact / 精确匹配",
            "Precision / 精确率",
            "Recall / 召回率",
            "F1",
            "Evidence / 证据",
        ],
        rows,
    )


def variability_table(summary: dict[str, Any]) -> str:
    rows = []
    for workflow in WORKFLOWS:
        across = summary["repetition"][workflow]["across_repetition_summary"]
        for metric, label in METRIC_NAMES.items():
            values = across[metric]
            rows.append(
                [
                    WORKFLOW_NAMES[workflow],
                    label,
                    pct(values["mean"]),
                    pct(values["sample_standard_deviation"]),
                    f"{pct(values['minimum'])}–{pct(values['maximum'])}",
                ]
            )
    return table(
        [
            "Workflow / 工作流",
            "Metric / 指标",
            "Mean / 均值",
            "Sample SD / 样本标准差",
            "Range / 范围",
        ],
        rows,
    )


def bootstrap_table(summary: dict[str, Any]) -> str:
    rows = []
    for pair_name, metrics in summary["uncertainty"]["pairs"].items():
        left, right = pair_name.split("_minus_")
        label = f"{WORKFLOW_NAMES[left]} − {WORKFLOW_NAMES[right]}"
        for metric, metric_label in METRIC_NAMES.items():
            result = metrics[metric]
            interval = result["percentile_95_interval"]
            rows.append(
                [
                    label,
                    metric_label,
                    pp(result["point_difference_left_minus_right"]),
                    f"[{pp(interval[0])}, {pp(interval[1])}]",
                ]
            )
    return table(
        [
            "Contrast / 对比",
            "Metric / 指标",
            "Point difference / 点估计差",
            "95% percentile interval / 百分位区间",
        ],
        rows,
    )


def category_table(summary: dict[str, Any]) -> str:
    categories = sorted(summary["per_category"][WORKFLOWS[0]])
    rows = []
    for category in categories:
        for workflow in WORKFLOWS:
            metrics = summary["per_category"][workflow][category]
            rows.append(
                [
                    category,
                    WORKFLOW_NAMES[workflow],
                    f"{metrics['candidate_count']}/{metrics['execution_count']}",
                    pct(metrics["status_accuracy"]),
                    pct(metrics["semantic_exact_match_accuracy"]),
                    pct(metrics["change_f1"]),
                    pct(metrics["evidence_support_rate"]),
                ]
            )
    return table(
        [
            "Category / 类别",
            "Workflow / 工作流",
            "Candidates / 候选",
            "Status / 状态",
            "Exact / 精确匹配",
            "F1",
            "Evidence / 证据",
        ],
        rows,
    )


def question_table(summary: dict[str, Any]) -> str:
    indexed = {
        workflow: {
            row["question_id"]: row
            for row in summary["question_success_frequency"][workflow]["questions"]
        }
        for workflow in WORKFLOWS
    }
    question_ids = sorted(indexed[WORKFLOWS[0]])
    rows = []
    for question_id in question_ids:
        direct = indexed["direct_llm"][question_id]
        rows.append(
            [
                question_id,
                direct["category"],
                str(direct["exact_success_frequency"]),
                str(indexed["tool_using_agent"][question_id]["exact_success_frequency"]),
                str(indexed["proposed"][question_id]["exact_success_frequency"]),
            ]
        )
    return table(
        [
            "Question / 问题",
            "Category / 类别",
            "Direct LLM",
            "Tool-Using Agent",
            "Proposed",
        ],
        rows,
    )


def audit_table(summary: dict[str, Any]) -> str:
    rows = []
    for workflow in WORKFLOWS:
        audit = summary["manual_audit"]["by_workflow"][workflow]
        counts = audit["claim_label_counts"]
        rows.append(
            [
                WORKFLOW_NAMES[workflow],
                f"{audit['audited_candidate_count']}/{audit['audited_execution_count']}",
                str(audit["atomic_claim_count"]),
                str(counts.get("supported", 0)),
                str(counts.get("unsupported", 0)),
                str(counts.get("indeterminate", 0)),
                pct(audit["unsupported_or_indeterminate_claim_rate"]),
                f"{audit['evidence_references_verified_count']}/{audit['audited_candidate_count']}",
                str(audit["safety_overreach_count"]),
            ]
        )
    return table(
        [
            "Workflow / 工作流",
            "Audited candidates / 审核候选",
            "Claims / 声明",
            "Supported / 支持",
            "Unsupported / 不支持",
            "Indeterminate / 不确定",
            "Unsupported + indeterminate / 不支持及不确定率",
            "Evidence verified / 证据核对通过",
            "Safety overreach / 安全越界",
        ],
        rows,
    )


def failure_frequency(summary: dict[str, Any]) -> str:
    rows = []
    for workflow in WORKFLOWS:
        distribution = summary["question_success_frequency"][workflow][
            "frequency_distribution"
        ]
        rows.append(
            [WORKFLOW_NAMES[workflow]]
            + [str(distribution[str(value)]) for value in range(4)]
        )
    return table(
        [
            "Workflow / 工作流",
            "0/3 exact",
            "1/3 exact",
            "2/3 exact",
            "3/3 exact",
        ],
        rows,
    )


def build_document() -> str:
    if sha256(SUMMARY_PATH) != EXPECTED_SUMMARY_SHA256:
        raise ValueError("Validated Gate 4 summary hash changed")
    if sha256(VALIDATION_PATH) != EXPECTED_VALIDATION_SHA256:
        raise ValueError("Gate 4 independent-validation hash changed")
    summary = load_json(SUMMARY_PATH)
    validation = load_json(VALIDATION_PATH)
    if validation["status"] != "PASS_WITH_RECORDED_DATA_LIMITATIONS":
        raise ValueError("Gate 4 validation status is not publication-draft ready")
    operations = summary["operations"]
    manual = summary["manual_audit"]["overall"]

    sections = [
        "# Gate 4 Controlled Held-Out Evaluation Results\n\n# Gate 4 受控留出评测结果",
        (
            "**Status: privately reviewed and explicitly approved for GitHub publication on 2026-08-11.**\n\n"
            "**状态：已完成私人审查，并于 2026-08-11 明确批准发布到 GitHub。**"
        ),
        "<!-- Exact tables are used instead of charts because the comparison has three workflows and the audit requires precise per-repetition, per-category, and per-question lookup. -->",
        (
            "## Proposed was strongest on structured answer accuracy in this controlled fixture\n\n"
            "## Proposed 在该受控样例的结构化答案准确性上表现最强\n\n"
            "Across 120 scheduled executions per workflow, Proposed achieved 96.67% semantic exact match and 97.90% change F1, compared with 84.17% and 91.85% for Tool-Using Agent and 54.17% and 63.16% for Direct LLM. Proposed also retained the highest completion rate at 98.33%. These are repeated results on one independently constructed synthetic held-out fixture, not a universal BIM benchmark.\n\n"
            "每个工作流包含 120 次计划执行。Proposed 的语义精确匹配率为 96.67%，Change F1 为 97.90%；Tool-Using Agent 分别为 84.17% 和 91.85%，Direct LLM 分别为 54.17% 和 63.16%。Proposed 还以 98.33% 保持最高完成率。这些数字只是一个独立构造的合成留出样例上的重复结果，不是通用 BIM 基准。\n\n"
            f"The deterministic scorer found 100% evidence support for Tool-Using Agent and Proposed predictions, but the blinded human audit was stricter about citation quality: {manual['evidence_references_verified_count']} of {manual['audited_candidate_count']} audited candidates passed citation verification. This distinction is preserved rather than merging machine evidence validation with human citation review.\n\n"
            f"确定性评分器认为 Tool-Using Agent 与 Proposed 的预测证据支持率均为 100%，但盲态人工审核对引用质量更严格：{manual['audited_candidate_count']} 个已审核候选中有 {manual['evidence_references_verified_count']} 个通过引用核对。本文保留机器证据验证与人工引用审核之间的区别，不将二者合并。"
        ),
        (
            "## Scope and metric definitions\n\n"
            "## 范围与指标定义\n\n"
            "The evaluation contains 40 English held-out questions, three frozen workflows, and three complete repetition blocks, for 360 primary executions. Completion uses all 40 scheduled questions per workflow and repetition as its denominator; an experimental failure counts as incomplete. Status accuracy compares `answered`, `not_found`, and `insufficient_evidence`. Semantic exact match requires both the correct status and the exact frozen structured change facts. Change precision, recall, and F1 use workflow-neutral structured fact identity. Deterministic evidence support checks cited structured evidence but does not score free-text semantics.\n\n"
            "本评测包含 40 道英文留出问题、三个冻结工作流和三个完整重复区组，共 360 次主执行。完成率以每个工作流、每次重复的全部 40 道计划问题为分母；实验失败计为未完成。状态准确率比较 `answered`、`not_found` 与 `insufficient_evidence`。语义精确匹配要求状态正确且冻结结构化变更事实完全一致。Change Precision、Recall 和 F1 使用与工作流无关的结构化事实身份。确定性证据支持检查所引用的结构化证据，但不评分自由文本语义。"
        ),
        "## Aggregate results across all three repetitions\n\n## 三次重复的总体结果\n\n" + overall_table(summary),
        (
            "The aggregate table treats each workflow's 120 scheduled executions as the comparison cohort. Missing candidates remain in completion, status, and exact-match denominators.\n\n"
            "总体表以每个工作流的 120 次计划执行作为比较集合。缺失候选仍保留在完成率、状态准确率和精确匹配率的分母中。"
        ),
        "## Per-repetition results show the retained run-to-run variation\n\n## 分重复结果展示保留的运行间变化\n\n" + repetition_table(summary),
        (
            "Each row contains one 40-question workflow/repetition block. The following table summarizes the three block-level values using their mean, sample standard deviation, and observed range.\n\n"
            "每一行对应一个包含 40 道问题的工作流/重复区组。下表使用三个区组级数值的均值、样本标准差和观测范围进行汇总。"
        ),
        variability_table(summary),
        (
            "## Clustered bootstrap preserves all repetitions for each sampled question\n\n"
            "## 聚类 Bootstrap 在抽样时保留每道问题的全部重复\n\n"
            "Pairwise differences use 2,000 question-clustered paired bootstrap resamples with fixed seed `20260808`. All three repetitions for a sampled question remain in the same cluster. The intervals quantify resampling uncertainty on this fixture; they are not standalone significance tests and do not justify external generalization.\n\n"
            "工作流两两差异使用固定 seed `20260808` 的 2,000 次问题聚类配对 Bootstrap。每道被抽中问题的三次重复始终保留在同一 cluster 中。这些区间量化该样例上的重采样不确定性；它们不是独立的显著性检验，也不能支持外部泛化。\n\n"
            + bootstrap_table(summary)
        ),
        (
            "## Category results retain the frozen question taxonomy\n\n"
            "## 分类结果保留冻结的问题分类体系\n\n"
            "Category-level values aggregate all three repetitions. They are descriptive cuts of the same 360 executions, not independent experiments.\n\n"
            "分类指标汇总三次重复。它们只是同一批 360 次执行的描述性切分，不是相互独立的实验。\n\n"
            + category_table(summary)
        ),
        (
            "## Exact success frequency exposes question-level repeatability\n\n"
            "## 精确成功频率揭示问题级重复性\n\n"
            "The distribution counts how many of the 40 questions achieved exact success zero, one, two, or three times for each workflow.\n\n"
            "该分布统计每个工作流中，40 道问题分别有多少道取得零次、一次、两次或三次精确成功。\n\n"
            + failure_frequency(summary)
            + "\n\nThe detailed table reports each question's exact-success frequency from 0 to 3.\n\n详细表列出每道问题从 0 到 3 的精确成功次数。\n\n"
            + question_table(summary)
        ),
        (
            "## The blinded manual audit found four unsupported or indeterminate claims\n\n"
            "## 盲态人工审核发现四条不支持或不确定声明\n\n"
            f"The preselected audit covered 135 executions: all nine workflow/repetition combinations for 15 question IDs. The project's available cross-domain reviewer completed an intensive short-duration review of {manual['atomic_claim_count']} atomic claims: {manual['claim_label_counts'].get('supported', 0)} supported, {manual['claim_label_counts'].get('unsupported', 0)} unsupported, and {manual['claim_label_counts'].get('indeterminate', 0)} indeterminate. The unsupported-or-indeterminate claim rate was {pct(manual['unsupported_or_indeterminate_claim_rate'])}. This full-coverage review represents substantial domain-and-code audit effort at the project's practical capacity. It is reported as a single-reviewer expert audit; a multi-rater agreement statistic is not applicable to this design.\n\n"
            f"预选审核覆盖 135 次执行，即 15 个问题 ID 的全部九个工作流/重复组合。项目当前可用的跨领域审核者在短时间内完成了高强度审核，共标注 {manual['atomic_claim_count']} 条原子声明：{manual['claim_label_counts'].get('supported', 0)} 条 supported、{manual['claim_label_counts'].get('unsupported', 0)} 条 unsupported、{manual['claim_label_counts'].get('indeterminate', 0)} 条 indeterminate。不支持或不确定声明率为 {pct(manual['unsupported_or_indeterminate_claim_rate'])}。这项全覆盖工作已经代表项目现实条件下相当可观的土木建筑领域与代码审计投入。本文将其如实表述为单审核者专家审核；多审核者一致性统计不适用于这一审核设计。\n\n"
            + audit_table(summary)
        ),
        (
            "## Operational accounting stayed below the frozen ceiling\n\n"
            "## 运行费用低于冻结上限\n\n"
            f"The final ledger records {operations['evaluation_wide_ledger']['request_attempts']} request attempts, {operations['evaluation_wide_ledger']['successful_responses']} successful responses, {operations['evaluation_wide_ledger']['input_tokens']:,} input tokens, {operations['evaluation_wide_ledger']['cached_input_tokens']:,} cached input tokens, and {operations['evaluation_wide_ledger']['output_tokens']:,} output tokens. Conservative estimated spend was CNY {operations['evaluation_wide_ledger']['conservative_estimated_cny']:.5f}, below the CNY {operations['evaluation_wide_ledger']['hard_ceiling_cny']:.2f} hard ceiling. Twelve non-retried experimental failures were all `schema_or_output_format`; Proposed used {operations['repair']['proposed_repair_count']} controlled repairs.\n\n"
            f"最终账本记录 {operations['evaluation_wide_ledger']['request_attempts']} 次请求尝试、{operations['evaluation_wide_ledger']['successful_responses']} 次成功响应、{operations['evaluation_wide_ledger']['input_tokens']:,} 个输入 token、{operations['evaluation_wide_ledger']['cached_input_tokens']:,} 个缓存输入 token 和 {operations['evaluation_wide_ledger']['output_tokens']:,} 个输出 token。保守估算费用为人民币 {operations['evaluation_wide_ledger']['conservative_estimated_cny']:.5f} 元，低于人民币 {operations['evaluation_wide_ledger']['hard_ceiling_cny']:.2f} 元硬上限。12 个未重试实验失败全部属于 `schema_or_output_format`；Proposed 使用了 {operations['repair']['proposed_repair_count']} 次受控修复。\n\n"
            f"DeepSeek was selected in substantial part for its open-source and open-weight ecosystem, high accessibility, and expected price-performance. Completing the full repeated evaluation—including validators, controlled repairs, and recovery accounting—for an authoritative conservative spend of only CNY {operations['evaluation_wide_ledger']['authoritative_spend_cny']:.5f} materially exceeded the project's cost expectations. The low spend is therefore a positive experimental outcome: it demonstrates that this evaluation design can be executed with unusually strong cost efficiency and a low practical adoption barrier.\n\n"
            f"选择 DeepSeek 的重要原因，本来就包括其开源与开放权重生态、高易用性以及预期中的高性价比。完整完成本次重复评测——包括 Validator、受控修复和恢复账本——权威保守费用仍只有人民币 {operations['evaluation_wide_ledger']['authoritative_spend_cny']:.5f} 元，明显优于项目原先的成本预期。因此，极低费用本身就是一项值得正面强调的实验结果：它表明这套评测设计具有超出预期的成本效率和很低的实际采用门槛。"
        ),
        (
            "## Limitations materially bound interpretation\n\n"
            "## 限制条件实质约束结果解释\n\n"
            "- The fixture is synthetic, independently constructed, and controlled; it does not represent arbitrary IFC models.\n  该样例为独立构造的受控合成数据，不能代表任意 IFC 模型。\n"
            "- The comparison covers three repetitions, one model provider, and only the frozen `added`, `deleted`, and `property_modified` change boundary.\n  对比只覆盖三次重复、一个模型提供商，以及冻结的 `added`、`deleted` 和 `property_modified` 变化边界。\n"
            "- Free-text semantics were not scored deterministically. The available cross-domain reviewer completed the full 135-execution expert audit; multi-rater agreement was outside this design and is not estimated.\n  自由文本语义未进行确定性评分。当前可用的跨领域审核者已完成全部 135 次执行的专家审核；多审核者一致性不属于本设计范围，因此未作估计。\n"
            "- Per-execution latency was not persisted and is unavailable; no estimated latency is substituted.\n  逐执行时延未被持久化，因此不可用；本文没有用估算时延替代。\n"
            "- Seven executions occupy three combined usage-attribution pools because four legacy failure rows lack cumulative token and cost metadata.\n  由于四个早期失败记录缺少累计 token 与费用元数据，七次执行只能保留在三个组合用量归属池中。\n"
            "- Token and cost cannot be split reliably by primary, validator, and repair call type from cumulative-only usage records.\n  仅凭累计用量记录，无法可靠地把 token 与费用拆分到主调用、Validator 和修复调用。\n"
            "- Bootstrap intervals describe uncertainty within this fixture and do not alone establish significance, causality, or generalizability.\n  Bootstrap 区间只描述该样例内部的不确定性，不能单独证明显著性、因果关系或可泛化性。"
        ),
        (
            "## Reproducibility and release boundary\n\n"
            "## 可复现性与发布边界\n\n"
            "The authoritative machine-readable sources are the [offline summary](../evals/results/held_out/gate4-controlled-heldout-v0.1.0/gate4-offline-summary.json), [independent validation](../evals/results/held_out/gate4-controlled-heldout-v0.1.0/gate4-independent-validation.json), [post-run audit](../evals/audits/held_out/gate4-post-run-audit.json), and [per-execution scores](../evals/results/held_out/gate4-controlled-heldout-v0.1.0/gate4-scored-executions.json). The independent validation status is `PASS_WITH_RECORDED_DATA_LIMITATIONS`.\n\n"
            "权威机器可读来源包括[离线汇总](../evals/results/held_out/gate4-controlled-heldout-v0.1.0/gate4-offline-summary.json)、[独立验证](../evals/results/held_out/gate4-controlled-heldout-v0.1.0/gate4-independent-validation.json)、[运行后审核](../evals/audits/held_out/gate4-post-run-audit.json)以及[逐执行评分](../evals/results/held_out/gate4-controlled-heldout-v0.1.0/gate4-scored-executions.json)。独立验证状态为 `PASS_WITH_RECORDED_DATA_LIMITATIONS`。\n\n"
            "This document completed private review and received explicit authorization for GitHub publication on 2026-08-11. Publication does not expand the evidence boundary: the results remain observations from one controlled synthetic fixture and must not be presented as a universal benchmark.\n\n"
            "本文已完成私人审查，并于 2026-08-11 获得明确的 GitHub 发布授权。发布不会扩大证据边界：这些结果仍只是一个受控合成样例上的观察，不得表述为通用基准。"
        ),
        (
            "## Recommended next step\n\n"
            "## 建议的下一步\n\n"
            "Publish the reviewed artifact while preserving the recorded limitations, frozen hashes, and reproducibility links. Any later experiment or claim expansion requires a separately declared design; no additional model calls or frozen-contract changes are needed for this release.\n\n"
            "发布已审核的产物，同时保留全部记录限制、冻结哈希和可复现链接。任何后续实验或结论扩展都需要另行声明设计；本次发布不需要新增模型调用，也不需要修改冻结契约。"
        ),
    ]
    return "\n\n".join(sections) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = build_document()
    if args.check:
        if not OUTPUT_PATH.is_file():
            raise FileNotFoundError(OUTPUT_PATH)
        if OUTPUT_PATH.read_text(encoding="utf-8") != rendered:
            raise ValueError("Gate 4 results document differs from deterministic output")
    else:
        OUTPUT_PATH.write_text(rendered, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "status": "PASS",
                "mode": "CHECK" if args.check else "WRITE",
                "output": OUTPUT_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
                "output_sha256": hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
                "source_summary_sha256": EXPECTED_SUMMARY_SHA256,
                "source_validation_sha256": EXPECTED_VALIDATION_SHA256,
                "public_release_authorized": True,
                "uploaded": False,
                "model_calls_made": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
