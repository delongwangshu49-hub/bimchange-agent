# Gate 4 Controlled Held-Out Evaluation Results

# Gate 4 受控留出评测结果

**Status: privately reviewed and explicitly approved for GitHub publication on 2026-08-11.**

**状态：已完成私人审查，并于 2026-08-11 明确批准发布到 GitHub。**

<!-- Exact tables are used instead of charts because the comparison has three workflows and the audit requires precise per-repetition, per-category, and per-question lookup. -->

## Proposed was strongest on structured answer accuracy in this controlled fixture

## Proposed 在该受控样例的结构化答案准确性上表现最强

Across 120 scheduled executions per workflow, Proposed achieved 96.67% semantic exact match and 97.90% change F1, compared with 84.17% and 91.85% for Tool-Using Agent and 54.17% and 63.16% for Direct LLM. Proposed also retained the highest completion rate at 98.33%. These are repeated results on one independently constructed synthetic held-out fixture, not a universal BIM benchmark.

每个工作流包含 120 次计划执行。Proposed 的语义精确匹配率为 96.67%，Change F1 为 97.90%；Tool-Using Agent 分别为 84.17% 和 91.85%，Direct LLM 分别为 54.17% 和 63.16%。Proposed 还以 98.33% 保持最高完成率。这些数字只是一个独立构造的合成留出样例上的重复结果，不是通用 BIM 基准。

The deterministic scorer found 100% evidence support for Tool-Using Agent and Proposed predictions, but the blinded human audit was stricter about citation quality: 90 of 131 audited candidates passed citation verification. This distinction is preserved rather than merging machine evidence validation with human citation review.

确定性评分器认为 Tool-Using Agent 与 Proposed 的预测证据支持率均为 100%，但盲态人工审核对引用质量更严格：131 个已审核候选中有 90 个通过引用核对。本文保留机器证据验证与人工引用审核之间的区别，不将二者合并。

## Scope and metric definitions

## 范围与指标定义

The evaluation contains 40 English held-out questions, three frozen workflows, and three complete repetition blocks, for 360 primary executions. Completion uses all 40 scheduled questions per workflow and repetition as its denominator; an experimental failure counts as incomplete. Status accuracy compares `answered`, `not_found`, and `insufficient_evidence`. Semantic exact match requires both the correct status and the exact frozen structured change facts. Change precision, recall, and F1 use workflow-neutral structured fact identity. Deterministic evidence support checks cited structured evidence but does not score free-text semantics.

本评测包含 40 道英文留出问题、三个冻结工作流和三个完整重复区组，共 360 次主执行。完成率以每个工作流、每次重复的全部 40 道计划问题为分母；实验失败计为未完成。状态准确率比较 `answered`、`not_found` 与 `insufficient_evidence`。语义精确匹配要求状态正确且冻结结构化变更事实完全一致。Change Precision、Recall 和 F1 使用与工作流无关的结构化事实身份。确定性证据支持检查所引用的结构化证据，但不评分自由文本语义。

## Aggregate results across all three repetitions

## 三次重复的总体结果

| Workflow / 工作流 | Candidates / 候选 | Completion / 完成率 | Status / 状态 | Exact / 精确匹配 | Precision / 精确率 | Recall / 召回率 | F1 | Evidence / 证据 |
|---|---|---|---|---|---|---|---|---|
| Direct LLM | 117/120 | 97.50% | 94.17% | 54.17% | 66.33% | 60.27% | 63.16% | 65.83% |
| Tool-Using Agent | 113/120 | 94.17% | 90.83% | 84.17% | 100.00% | 84.93% | 91.85% | 100.00% |
| Proposed | 118/120 | 98.33% | 96.67% | 96.67% | 100.00% | 95.89% | 97.90% | 100.00% |

The aggregate table treats each workflow's 120 scheduled executions as the comparison cohort. Missing candidates remain in completion, status, and exact-match denominators.

总体表以每个工作流的 120 次计划执行作为比较集合。缺失候选仍保留在完成率、状态准确率和精确匹配率的分母中。

## Per-repetition results show the retained run-to-run variation

## 分重复结果展示保留的运行间变化

| Workflow / 工作流 | Rep / 重复 | Candidates / 候选 | Status / 状态 | Exact / 精确匹配 | Precision / 精确率 | Recall / 召回率 | F1 | Evidence / 证据 |
|---|---|---|---|---|---|---|---|---|
| Direct LLM | 1 | 40/40 | 95.00% | 50.00% | 61.64% | 61.64% | 61.64% | 60.27% |
| Direct LLM | 2 | 38/40 | 92.50% | 52.50% | 64.91% | 50.68% | 56.92% | 64.91% |
| Direct LLM | 3 | 39/40 | 95.00% | 60.00% | 72.46% | 68.49% | 70.42% | 72.46% |
| Tool-Using Agent | 1 | 36/40 | 87.50% | 80.00% | 100.00% | 83.56% | 91.04% | 100.00% |
| Tool-Using Agent | 2 | 39/40 | 92.50% | 87.50% | 100.00% | 90.41% | 94.96% | 100.00% |
| Tool-Using Agent | 3 | 38/40 | 92.50% | 85.00% | 100.00% | 80.82% | 89.39% | 100.00% |
| Proposed | 1 | 40/40 | 97.50% | 97.50% | 100.00% | 94.52% | 97.18% | 100.00% |
| Proposed | 2 | 39/40 | 95.00% | 95.00% | 100.00% | 93.15% | 96.45% | 100.00% |
| Proposed | 3 | 39/40 | 97.50% | 97.50% | 100.00% | 100.00% | 100.00% | 100.00% |

Each row contains one 40-question workflow/repetition block. The following table summarizes the three block-level values using their mean, sample standard deviation, and observed range.

每一行对应一个包含 40 道问题的工作流/重复区组。下表使用三个区组级数值的均值、样本标准差和观测范围进行汇总。

| Workflow / 工作流 | Metric / 指标 | Mean / 均值 | Sample SD / 样本标准差 | Range / 范围 |
|---|---|---|---|---|
| Direct LLM | Completion rate / 完成率 | 97.50% | 2.50% | 95.00%–100.00% |
| Direct LLM | Status accuracy / 状态准确率 | 94.17% | 1.44% | 92.50%–95.00% |
| Direct LLM | Semantic exact match / 语义精确匹配 | 54.17% | 5.20% | 50.00%–60.00% |
| Direct LLM | Change precision / 变更精确率 | 66.34% | 5.55% | 61.64%–72.46% |
| Direct LLM | Change recall / 变更召回率 | 60.27% | 8.98% | 50.68%–68.49% |
| Direct LLM | Change F1 / 变更 F1 | 63.00% | 6.85% | 56.92%–70.42% |
| Direct LLM | Deterministic evidence support / 确定性证据支持率 | 65.88% | 6.15% | 60.27%–72.46% |
| Tool-Using Agent | Completion rate / 完成率 | 94.17% | 3.82% | 90.00%–97.50% |
| Tool-Using Agent | Status accuracy / 状态准确率 | 90.83% | 2.89% | 87.50%–92.50% |
| Tool-Using Agent | Semantic exact match / 语义精确匹配 | 84.17% | 3.82% | 80.00%–87.50% |
| Tool-Using Agent | Change precision / 变更精确率 | 100.00% | 0.00% | 100.00%–100.00% |
| Tool-Using Agent | Change recall / 变更召回率 | 84.93% | 4.94% | 80.82%–90.41% |
| Tool-Using Agent | Change F1 / 变更 F1 | 91.80% | 2.86% | 89.39%–94.96% |
| Tool-Using Agent | Deterministic evidence support / 确定性证据支持率 | 100.00% | 0.00% | 100.00%–100.00% |
| Proposed | Completion rate / 完成率 | 98.33% | 1.44% | 97.50%–100.00% |
| Proposed | Status accuracy / 状态准确率 | 96.67% | 1.44% | 95.00%–97.50% |
| Proposed | Semantic exact match / 语义精确匹配 | 96.67% | 1.44% | 95.00%–97.50% |
| Proposed | Change precision / 变更精确率 | 100.00% | 0.00% | 100.00%–100.00% |
| Proposed | Change recall / 变更召回率 | 95.89% | 3.62% | 93.15%–100.00% |
| Proposed | Change F1 / 变更 F1 | 97.88% | 1.87% | 96.45%–100.00% |
| Proposed | Deterministic evidence support / 确定性证据支持率 | 100.00% | 0.00% | 100.00%–100.00% |

## Clustered bootstrap preserves all repetitions for each sampled question

## 聚类 Bootstrap 在抽样时保留每道问题的全部重复

Pairwise differences use 2,000 question-clustered paired bootstrap resamples with fixed seed `20260808`. All three repetitions for a sampled question remain in the same cluster. The intervals quantify resampling uncertainty on this fixture; they are not standalone significance tests and do not justify external generalization.

工作流两两差异使用固定 seed `20260808` 的 2,000 次问题聚类配对 Bootstrap。每道被抽中问题的三次重复始终保留在同一 cluster 中。这些区间量化该样例上的重采样不确定性；它们不是独立的显著性检验，也不能支持外部泛化。

| Contrast / 对比 | Metric / 指标 | Point difference / 点估计差 | 95% percentile interval / 百分位区间 |
|---|---|---|---|
| Direct LLM − Tool-Using Agent | Completion rate / 完成率 | +3.33 pp | [-2.50 pp, +8.33 pp] |
| Direct LLM − Tool-Using Agent | Status accuracy / 状态准确率 | +3.33 pp | [-5.83 pp, +11.67 pp] |
| Direct LLM − Tool-Using Agent | Semantic exact match / 语义精确匹配 | -30.00 pp | [-46.67 pp, -12.50 pp] |
| Direct LLM − Tool-Using Agent | Change precision / 变更精确率 | -33.67 pp | [-45.19 pp, -23.74 pp] |
| Direct LLM − Tool-Using Agent | Change recall / 变更召回率 | -24.66 pp | [-41.67 pp, -4.90 pp] |
| Direct LLM − Tool-Using Agent | Change F1 / 变更 F1 | -28.69 pp | [-41.59 pp, -13.99 pp] |
| Direct LLM − Tool-Using Agent | Deterministic evidence support / 确定性证据支持率 | -34.17 pp | [-45.81 pp, -24.20 pp] |
| Direct LLM − Proposed | Completion rate / 完成率 | -0.83 pp | [-5.00 pp, +3.33 pp] |
| Direct LLM − Proposed | Status accuracy / 状态准确率 | -2.50 pp | [-10.00 pp, +4.17 pp] |
| Direct LLM − Proposed | Semantic exact match / 语义精确匹配 | -42.50 pp | [-55.83 pp, -30.00 pp] |
| Direct LLM − Proposed | Change precision / 变更精确率 | -33.67 pp | [-45.19 pp, -23.74 pp] |
| Direct LLM − Proposed | Change recall / 变更召回率 | -35.62 pp | [-48.61 pp, -21.39 pp] |
| Direct LLM − Proposed | Change F1 / 变更 F1 | -34.74 pp | [-45.79 pp, -23.38 pp] |
| Direct LLM − Proposed | Deterministic evidence support / 确定性证据支持率 | -34.17 pp | [-45.81 pp, -24.20 pp] |
| Tool-Using Agent − Proposed | Completion rate / 完成率 | -4.17 pp | [-9.17 pp, +0.00 pp] |
| Tool-Using Agent − Proposed | Status accuracy / 状态准确率 | -5.83 pp | [-10.83 pp, -0.83 pp] |
| Tool-Using Agent − Proposed | Semantic exact match / 语义精确匹配 | -12.50 pp | [-20.83 pp, -5.00 pp] |
| Tool-Using Agent − Proposed | Change precision / 变更精确率 | +0.00 pp | [+0.00 pp, +0.00 pp] |
| Tool-Using Agent − Proposed | Change recall / 变更召回率 | -10.96 pp | [-18.57 pp, -4.62 pp] |
| Tool-Using Agent − Proposed | Change F1 / 变更 F1 | -6.05 pp | [-11.06 pp, -2.38 pp] |
| Tool-Using Agent − Proposed | Deterministic evidence support / 确定性证据支持率 | +0.00 pp | [+0.00 pp, +0.00 pp] |

## Category results retain the frozen question taxonomy

## 分类结果保留冻结的问题分类体系

Category-level values aggregate all three repetitions. They are descriptive cuts of the same 360 executions, not independent experiments.

分类指标汇总三次重复。它们只是同一批 360 次执行的描述性切分，不是相互独立的实验。

| Category / 类别 | Workflow / 工作流 | Candidates / 候选 | Status / 状态 | Exact / 精确匹配 | F1 | Evidence / 证据 |
|---|---|---|---|---|---|---|
| evidence_boundary | Direct LLM | 15/15 | 100.00% | 86.67% | 86.67% | 86.67% |
| evidence_boundary | Tool-Using Agent | 15/15 | 93.33% | 40.00% | 63.64% | 100.00% |
| evidence_boundary | Proposed | 15/15 | 100.00% | 100.00% | 100.00% | 100.00% |
| fact_lookup | Direct LLM | 18/18 | 100.00% | 77.78% | 77.78% | 72.22% |
| fact_lookup | Tool-Using Agent | 16/18 | 88.89% | 88.89% | 94.12% | 100.00% |
| fact_lookup | Proposed | 18/18 | 100.00% | 100.00% | 100.00% | 100.00% |
| filtered_lookup | Direct LLM | 42/42 | 100.00% | 45.24% | 67.74% | 67.74% |
| filtered_lookup | Tool-Using Agent | 41/42 | 90.48% | 90.48% | 91.23% | 100.00% |
| filtered_lookup | Proposed | 42/42 | 95.24% | 95.24% | 95.51% | 100.00% |
| negative_control | Direct LLM | 15/15 | 73.33% | 73.33% | 100.00% | 100.00% |
| negative_control | Tool-Using Agent | 13/15 | 86.67% | 86.67% | 100.00% | 100.00% |
| negative_control | Proposed | 14/15 | 93.33% | 93.33% | 100.00% | 100.00% |
| property_change | Direct LLM | 18/18 | 100.00% | 11.11% | 9.52% | 9.52% |
| property_change | Tool-Using Agent | 18/18 | 100.00% | 100.00% | 100.00% | 100.00% |
| property_change | Proposed | 17/18 | 94.44% | 94.44% | 97.56% | 100.00% |
| summary | Direct LLM | 9/12 | 75.00% | 50.00% | 64.52% | 76.92% |
| summary | Tool-Using Agent | 10/12 | 83.33% | 83.33% | 94.12% | 100.00% |
| summary | Proposed | 12/12 | 100.00% | 100.00% | 100.00% | 100.00% |

## Exact success frequency exposes question-level repeatability

## 精确成功频率揭示问题级重复性

The distribution counts how many of the 40 questions achieved exact success zero, one, two, or three times for each workflow.

该分布统计每个工作流中，40 道问题分别有多少道取得零次、一次、两次或三次精确成功。

| Workflow / 工作流 | 0/3 exact | 1/3 exact | 2/3 exact | 3/3 exact |
|---|---|---|---|---|
| Direct LLM | 14 | 5 | 3 | 18 |
| Tool-Using Agent | 2 | 3 | 7 | 28 |
| Proposed | 0 | 1 | 2 | 37 |

The detailed table reports each question's exact-success frequency from 0 to 3.

详细表列出每道问题从 0 到 3 的精确成功次数。

| Question / 问题 | Category / 类别 | Direct LLM | Tool-Using Agent | Proposed |
|---|---|---|---|---|
| gate3-q09-all-changes | summary | 0 | 3 | 3 |
| gate3-q10-added-summary | summary | 3 | 2 | 3 |
| gate3-q11-deleted-summary | summary | 3 | 2 | 3 |
| gate3-q12-property-summary | summary | 0 | 3 | 3 |
| gate3-q13-beam-ground-guid | fact_lookup | 3 | 2 | 3 |
| gate3-q14-wall-ground-guid | fact_lookup | 3 | 3 | 3 |
| gate3-q15-column-level01-guid | fact_lookup | 3 | 3 | 3 |
| gate3-q16-slab-level01-guid | fact_lookup | 2 | 2 | 3 |
| gate3-q17-beam-roof-guid | fact_lookup | 0 | 3 | 3 |
| gate3-q18-wall-roof-guid | fact_lookup | 3 | 3 | 3 |
| gate3-q19-beam-filter | filtered_lookup | 0 | 2 | 3 |
| gate3-q20-column-filter | filtered_lookup | 0 | 3 | 3 |
| gate3-q21-wall-filter | filtered_lookup | 1 | 3 | 3 |
| gate3-q22-slab-filter | filtered_lookup | 2 | 3 | 3 |
| gate3-q23-ground-filter | filtered_lookup | 0 | 3 | 3 |
| gate3-q24-level01-filter | filtered_lookup | 1 | 3 | 3 |
| gate3-q25-roof-filter | filtered_lookup | 0 | 0 | 1 |
| gate3-q26-added-beam-filter | filtered_lookup | 3 | 3 | 3 |
| gate3-q27-deleted-column-filter | filtered_lookup | 3 | 3 | 3 |
| gate3-q28-property-wall-filter | filtered_lookup | 0 | 3 | 3 |
| gate3-q29-beam-roof-filter | filtered_lookup | 0 | 3 | 3 |
| gate3-q30-slab-ground-filter | filtered_lookup | 3 | 3 | 3 |
| gate3-q31-added-column-level01 | filtered_lookup | 3 | 3 | 3 |
| gate3-q32-deleted-wall-ground | filtered_lookup | 3 | 3 | 3 |
| gate3-q33-column-property | property_change | 1 | 3 | 3 |
| gate3-q34-wall-property | property_change | 0 | 3 | 2 |
| gate3-q35-beam-property | property_change | 0 | 3 | 3 |
| gate3-q36-slab-property | property_change | 0 | 3 | 3 |
| gate3-q37-loadbearing-properties | property_change | 0 | 3 | 3 |
| gate3-q38-wall-pset-property | property_change | 1 | 3 | 3 |
| gate3-q39-no-geometry | negative_control | 0 | 3 | 3 |
| gate3-q40-no-added-beam-roof | negative_control | 3 | 2 | 3 |
| gate3-q41-absent-guid | negative_control | 3 | 3 | 2 |
| gate3-q42-no-deleted-column-ground | negative_control | 2 | 3 | 3 |
| gate3-q43-no-property-slab-level01 | negative_control | 3 | 2 | 3 |
| gate3-q44-wall-safety-boundary | evidence_boundary | 3 | 3 | 3 |
| gate3-q45-fire-compliance-boundary | evidence_boundary | 1 | 1 | 3 |
| gate3-q46-beam-responsibility-boundary | evidence_boundary | 3 | 1 | 3 |
| gate3-q47-slab-priority-boundary | evidence_boundary | 3 | 1 | 3 |
| gate3-q48-wall-constructability-boundary | evidence_boundary | 3 | 0 | 3 |

## The blinded manual audit found four unsupported or indeterminate claims

## 盲态人工审核发现四条不支持或不确定声明

The preselected audit covered 135 executions: all nine workflow/repetition combinations for 15 question IDs. The project's available cross-domain reviewer completed an intensive short-duration review of 505 atomic claims: 501 supported, 1 unsupported, and 3 indeterminate. The unsupported-or-indeterminate claim rate was 0.79%. This full-coverage review represents substantial domain-and-code audit effort at the project's practical capacity. It is reported as a single-reviewer expert audit; a multi-rater agreement statistic is not applicable to this design.

预选审核覆盖 135 次执行，即 15 个问题 ID 的全部九个工作流/重复组合。项目当前可用的跨领域审核者在短时间内完成了高强度审核，共标注 505 条原子声明：501 条 supported、1 条 unsupported、3 条 indeterminate。不支持或不确定声明率为 0.79%。这项全覆盖工作已经代表项目现实条件下相当可观的土木建筑领域与代码审计投入。本文将其如实表述为单审核者专家审核；多审核者一致性统计不适用于这一审核设计。

| Workflow / 工作流 | Audited candidates / 审核候选 | Claims / 声明 | Supported / 支持 | Unsupported / 不支持 | Indeterminate / 不确定 | Unsupported + indeterminate / 不支持及不确定率 | Evidence verified / 证据核对通过 | Safety overreach / 安全越界 |
|---|---|---|---|---|---|---|---|---|
| Direct LLM | 43/45 | 166 | 163 | 0 | 3 | 1.81% | 6/43 | 0 |
| Tool-Using Agent | 43/45 | 167 | 166 | 1 | 0 | 0.60% | 42/43 | 1 |
| Proposed | 45/45 | 172 | 172 | 0 | 0 | 0.00% | 42/45 | 0 |

## Operational accounting stayed below the frozen ceiling

## 运行费用低于冻结上限

The final ledger records 758 request attempts, 748 successful responses, 3,158,978 input tokens, 2,322,176 cached input tokens, and 1,227,059 output tokens. Conservative estimated spend was CNY 4.67232, below the CNY 25.00 hard ceiling. Twelve non-retried experimental failures were all `schema_or_output_format`; Proposed used 8 controlled repairs.

最终账本记录 758 次请求尝试、748 次成功响应、3,158,978 个输入 token、2,322,176 个缓存输入 token 和 1,227,059 个输出 token。保守估算费用为人民币 4.67232 元，低于人民币 25.00 元硬上限。12 个未重试实验失败全部属于 `schema_or_output_format`；Proposed 使用了 8 次受控修复。

DeepSeek was selected in substantial part for its open-source and open-weight ecosystem, high accessibility, and expected price-performance. Completing the full repeated evaluation—including validators, controlled repairs, and recovery accounting—for an authoritative conservative spend of only CNY 4.67232 materially exceeded the project's cost expectations. The low spend is therefore a positive experimental outcome: it demonstrates that this evaluation design can be executed with unusually strong cost efficiency and a low practical adoption barrier.

选择 DeepSeek 的重要原因，本来就包括其开源与开放权重生态、高易用性以及预期中的高性价比。完整完成本次重复评测——包括 Validator、受控修复和恢复账本——权威保守费用仍只有人民币 4.67232 元，明显优于项目原先的成本预期。因此，极低费用本身就是一项值得正面强调的实验结果：它表明这套评测设计具有超出预期的成本效率和很低的实际采用门槛。

## Limitations materially bound interpretation

## 限制条件实质约束结果解释

- The fixture is synthetic, independently constructed, and controlled; it does not represent arbitrary IFC models.
  该样例为独立构造的受控合成数据，不能代表任意 IFC 模型。
- The comparison covers three repetitions, one model provider, and only the frozen `added`, `deleted`, and `property_modified` change boundary.
  对比只覆盖三次重复、一个模型提供商，以及冻结的 `added`、`deleted` 和 `property_modified` 变化边界。
- Free-text semantics were not scored deterministically. The available cross-domain reviewer completed the full 135-execution expert audit; multi-rater agreement was outside this design and is not estimated.
  自由文本语义未进行确定性评分。当前可用的跨领域审核者已完成全部 135 次执行的专家审核；多审核者一致性不属于本设计范围，因此未作估计。
- Per-execution latency was not persisted and is unavailable; no estimated latency is substituted.
  逐执行时延未被持久化，因此不可用；本文没有用估算时延替代。
- Seven executions occupy three combined usage-attribution pools because four legacy failure rows lack cumulative token and cost metadata.
  由于四个早期失败记录缺少累计 token 与费用元数据，七次执行只能保留在三个组合用量归属池中。
- Token and cost cannot be split reliably by primary, validator, and repair call type from cumulative-only usage records.
  仅凭累计用量记录，无法可靠地把 token 与费用拆分到主调用、Validator 和修复调用。
- Bootstrap intervals describe uncertainty within this fixture and do not alone establish significance, causality, or generalizability.
  Bootstrap 区间只描述该样例内部的不确定性，不能单独证明显著性、因果关系或可泛化性。

## Reproducibility and release boundary

## 可复现性与发布边界

The authoritative machine-readable sources are the [offline summary](../evals/results/held_out/gate4-controlled-heldout-v0.1.0/gate4-offline-summary.json), [independent validation](../evals/results/held_out/gate4-controlled-heldout-v0.1.0/gate4-independent-validation.json), [post-run audit](../evals/audits/held_out/gate4-post-run-audit.json), and [per-execution scores](../evals/results/held_out/gate4-controlled-heldout-v0.1.0/gate4-scored-executions.json). The independent validation status is `PASS_WITH_RECORDED_DATA_LIMITATIONS`.

权威机器可读来源包括[离线汇总](../evals/results/held_out/gate4-controlled-heldout-v0.1.0/gate4-offline-summary.json)、[独立验证](../evals/results/held_out/gate4-controlled-heldout-v0.1.0/gate4-independent-validation.json)、[运行后审核](../evals/audits/held_out/gate4-post-run-audit.json)以及[逐执行评分](../evals/results/held_out/gate4-controlled-heldout-v0.1.0/gate4-scored-executions.json)。独立验证状态为 `PASS_WITH_RECORDED_DATA_LIMITATIONS`。

This document completed private review and received explicit authorization for GitHub publication on 2026-08-11. Publication does not expand the evidence boundary: the results remain observations from one controlled synthetic fixture and must not be presented as a universal benchmark.

本文已完成私人审查，并于 2026-08-11 获得明确的 GitHub 发布授权。发布不会扩大证据边界：这些结果仍只是一个受控合成样例上的观察，不得表述为通用基准。

## Recommended next step

## 建议的下一步

Publish the reviewed artifact while preserving the recorded limitations, frozen hashes, and reproducibility links. Any later experiment or claim expansion requires a separately declared design; no additional model calls or frozen-contract changes are needed for this release.

发布已审核的产物，同时保留全部记录限制、冻结哈希和可复现链接。任何后续实验或结论扩展都需要另行声明设计；本次发布不需要新增模型调用，也不需要修改冻结契约。
