# BIMChange-Agent: Public Project Plan / 公开项目计划

> **Status:** Gate 3 development prototype complete; Gate 4 independent evaluation is next.<br>
> **Last updated:** 2026-08-07
>
> **状态：** Gate 3 开发原型已完成；下一阶段为 Gate 4 独立评测。<br>
> **最后更新：** 2026-08-07

## Research Goal / 研究目标

Building projects often contain several revisions of the same BIM model. Deterministic IFC tools can identify low-level differences, but their output may be difficult to interpret; direct language-model explanations can instead be fluent but unsupported.

建筑项目通常包含同一 BIM 模型的多个版本。确定性 IFC 工具能够识别底层差异，但其输出可能难以理解；直接使用语言模型生成说明，则可能出现表达流畅但缺乏证据的问题。

BIMChange-Agent studies whether an AI agent can transform deterministic IFC revision data into natural-language explanations while preserving traceable evidence for every material claim.

BIMChange-Agent 研究 AI 智能体能否把确定性的 IFC 版本数据转化为自然语言说明，同时为每项关键结论保留可追溯证据。

## Research Questions / 研究问题

1. Does deterministic IFC grounding improve change identification over a direct language-model baseline?<br>
   以确定性 IFC 数据为依据，能否比直接语言模型基线更准确地识别变更？
2. Does claim and evidence validation improve support accuracy and multi-step task success?<br>
   声明与证据验证能否提高证据支持准确率及多步骤任务成功率？
3. Are the reliability gains worth the additional latency and model-call cost?<br>
   可靠性提升是否值得额外的延迟与模型调用成本？
4. Do the results persist on an independently created held-out set?<br>
   这些结果能否在独立建立的留出集上保持？

These are research questions rather than assumed conclusions.

以上内容是待验证的研究问题，并非预设结论。

## Workflow / 工作流

1. **Query planning** — identify requested change types, IFC entities, locations, and evidence needs.<br>
   **查询规划** — 明确所需变更类型、IFC 实体、位置与证据要求。
2. **Deterministic IFC analysis** — compare model versions with established IFC tooling.<br>
   **确定性 IFC 分析** — 使用成熟 IFC 工具比较模型版本。
3. **Structured Change Records** — normalize additions, deletions, and modifications into auditable records.<br>
   **结构化 Change Record** — 将新增、删除与修改规范化为可审计记录。
4. **Evidence-grounded explanation** — produce user-facing language from verified records.<br>
   **基于证据的说明** — 根据已验证记录生成人类可读说明。
5. **Validation and bounded repair** — check schema, evidence coverage, and atomic claims, with at most one controlled repair in the Proposed workflow.<br>
   **验证与有限修复** — 检查 Schema、证据覆盖及原子声明；Proposed 流程最多允许一次受控修复。

## Evaluation Design / 评测设计

Three workflows share a common output contract and development question set: Direct LLM receives a non-diff model summary; Tool-Using Agent can query deterministic Change Records; Proposed adds validation and one bounded repair opportunity.

三种流程使用统一输出契约与开发问题集：Direct LLM 接收不含差异结论的模型摘要；Tool-Using Agent 可查询确定性的 Change Record；Proposed 在此基础上增加验证与一次有限修复机会。

Primary measures include completion, answer-status accuracy, exact structured match, change precision/recall/F1, evidence-support rate, response usage, estimated cost, and failure categories.

主要指标包括完成率、答案状态准确率、结构化精确匹配、变更精确率/召回率/F1、证据支持率、响应使用量、估算成本与失败类型。

## Decision Gates / 决策门

- **Gate 1 — Technical feasibility: complete.** Public IFC4 loading and deterministic property-change verification work on Windows.<br>
  **Gate 1 — 技术可行性：已完成。** 已在 Windows 上完成公开 IFC4 读取与确定性属性变更验证。
- **Gate 2 — Data and reference answers: complete.** A controlled three-change revision is normalized and checked against IFC files and IfcDiff output.<br>
  **Gate 2 — 数据与参考答案：已完成。** 受控三变更版本已完成规范化，并与 IFC 文件及 IfcDiff 输出核验。
- **Gate 3 — Agent prototype: complete for development scope.** Three workflows run on eight development questions with common schemas and scoring.<br>
  **Gate 3 — 智能体原型：开发范围内已完成。** 三种流程已在八道开发问题上运行，并使用统一 Schema 与评分机制。
- **Gate 4 — Evaluation and release: next.** Freeze contracts, build an independent held-out set, run repetitions, analyze failures, and prepare release documentation.<br>
  **Gate 4 — 评测与发布：下一阶段。** 冻结契约，建立独立留出集，进行重复实验、失败分析并准备发布文档。

## Current Evidence and Limits / 当前证据与局限

The Gate 3 development run indicates that deterministic tool access and validation can improve structured correctness and evidence support on the current controlled set. Detailed figures are recorded in [docs/gate3-development-results.md](docs/gate3-development-results.md).

Gate 3 开发运行表明，在当前受控数据集上，确定性工具访问与验证有望提升结构化正确性和证据支持率。详细数据见 [docs/gate3-development-results.md](docs/gate3-development-results.md)。

The development questions and workflow contracts were iteratively refined together. The results are therefore not held-out evidence, include one retained answer per question and condition, and do not establish general performance.

开发问题与工作流契约经历了同步迭代，因此现有结果不是独立留出证据；每个问题与条件仅保留一次最终答案，也不能证明通用性能。

The current data contain three Change Records from one small, single-storey IFC sample. Geometry changes, relationship changes, larger or multi-storey projects, additional IFC schemas, independent claim validation, and cross-model replication remain future work.

当前数据来自一个小型单层 IFC 样本，仅包含三条 Change Record。几何变更、关系变更、更大或多层项目、其他 IFC Schema、独立声明验证及跨模型复验仍属于后续工作。

## Data and Scope Boundaries / 数据与范围边界

Only public, clearly licensed, or programmatically generated IFC data are used. No confidential or proprietary project data are included.

项目仅使用公开、许可清晰或程序生成的 IFC 数据，不包含任何机密或专有项目数据。

The prototype does not train a foundation model, replace BIM authoring software, replace professional engineering review, or perform structural-safety or regulatory-compliance certification.

本原型不训练基础模型，不替代 BIM 创作软件或专业工程审查，也不执行结构安全或法规合规认证。

## Next Milestone / 下一里程碑

Freeze the Gate 3 prompts, schemas, and workflow logic before inspecting held-out outcomes. Then create a separate controlled revision and question set, run repeated comparisons without tuning on held-out results, and publish uncertainty and failure analysis alongside aggregate metrics.

在查看留出集结果前，先冻结 Gate 3 的提示词、Schema 与工作流逻辑；随后建立独立的受控版本与问题集，在不根据留出结果调参的前提下进行重复对比，并与汇总指标一同发布不确定性和失败分析。
