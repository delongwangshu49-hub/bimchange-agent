# Gate 4 Independent Held-Out Data and Question Design Specification

# Gate 4 独立留出数据与问题设计规格

## Status

This specification passed content and publication review and was frozen on 2026-08-08. It does not authorize model calls. The public Gate 3 baseline remains commit `abcb095`.

本规格已于 2026-08-08 完成内容与发布审核并冻结。当前仍不授权发起模型调用，Gate 3 的公开基线仍为提交 `abcb095`。

No Gate 3 prompt, JSON Schema, workflow logic, or scoring rule may be changed while this draft is reviewed or during the later held-out evaluation. A Gate 4 orchestration wrapper may be added after this specification is frozen, but it must call the frozen Gate 3 question-level functions without editing them and must reproduce the retained Gate 3 development artifacts before it is allowed to read held-out inputs.

在本草案审核期间以及后续留出评测期间，不得修改 Gate 3 的提示词、JSON Schema、工作流逻辑或评分规则。本规格冻结后可以增加 Gate 4 编排外壳，但它必须在不编辑 Gate 3 逐问题函数的前提下直接调用这些冻结函数，并先复现已保留的 Gate 3 开发产物，之后才允许读取留出输入。

The wrapper must be a new file. Protected Gate 3 source and Schema files remain byte-identical to `abcb095`. If the frozen prompt requires a fixed runtime source path, the wrapper must use an isolated staging directory that maps held-out artifacts to that path; the logical held-out artifacts and their hashes remain separate, and the public development files are not overwritten.

该外壳必须使用新文件实现。受保护的 Gate 3 源代码与 Schema 文件必须与 `abcb095` 保持字节一致。如果冻结提示词要求固定的运行时来源路径，外壳必须使用隔离的暂存目录把留出产物映射到该路径；逻辑上的留出产物及其哈希继续独立保存，公开开发文件不得被覆盖。

## 1. Evaluation objective and independence boundary

The objective is to compare the frozen Direct LLM, Tool-Using Agent, and Proposed workflows on a separately created IFC revision and English question set that were not used to tune Gate 3. The evaluation measures performance on this controlled held-out set; it is not a claim of universal BIM performance or a formal benchmark for arbitrary IFC models.

本评测的目标，是在独立建立、未用于 Gate 3 调优的 IFC 修订与英文问题集上，对冻结的 Direct LLM、Tool-Using Agent 和 Proposed 三种工作流进行比较。评测只衡量它们在该受控留出集上的表现，不代表通用 BIM 性能，也不是面向任意 IFC 模型的正式基准。

Independence is defined operationally:

独立性按以下可执行规则定义：

- held-out IFC files, Change Records, questions, and reference answers use new identifiers and paths;
  留出 IFC 文件、Change Record、问题与参考答案使用全新的标识符和路径；
- no held-out question repeats a Gate 3 development question verbatim;
  任何留出问题均不得逐字复用 Gate 3 开发问题；
- reference answers are generated without an LLM and are never included in model input;
  参考答案不调用 LLM 生成，也绝不进入模型输入；
- prompts and workflow behavior remain fixed before any held-out output is viewed;
  在查看任何留出输出前，提示词与工作流行为保持冻结；
- held-out outcomes may inform failure analysis, but they may not be used to tune the frozen comparison.
  留出结果可以用于失败分析，但不得用于调优已冻结的对比方案。

## 2. Data-source decision and licensing

### 2.1 Selected source strategy

The primary Gate 4 fixture will be a new deterministic IFC4 model generated from scratch with IfcOpenShell 0.8.5. It will not copy geometry, GlobalIds, names, or property values from the Gate 2 `Building-Structural.ifc` fixture. This choice provides a genuinely separate model while avoiding an incompatible external file and an ambiguous derivative-data boundary.

Gate 4 主数据将采用 IfcOpenShell 0.8.5 从零确定性生成的新 IFC4 模型。它不会复制 Gate 2 `Building-Structural.ifc` 样例的几何、GlobalId、名称或属性值。该选择既能提供真正独立的模型，也能避免外部文件兼容性问题与衍生数据许可边界不清。

The generator code remains under the repository's MIT license. The generated Gate 4 dataset artifacts will be explicitly released under Creative Commons Attribution 4.0 International (CC BY 4.0), attributed only to the project name: “BIMChange-Agent Gate 4 Held-Out Dataset.” No personal attribution is required in public text.

生成器代码继续使用仓库的 MIT 许可证。生成的 Gate 4 数据产物将明确采用 Creative Commons Attribution 4.0 International（CC BY 4.0）发布，署名仅使用项目名称“BIMChange-Agent Gate 4 Held-Out Dataset”，公开内容不要求个人署名。

The data documentation must distinguish the dataset license from the software license and must state that all changes are synthetic test fixtures, not engineering, constructability, compliance, or safety recommendations.

数据文档必须区分数据许可证与软件许可证，并明确所有变更仅为合成测试样例，不构成工程、可施工性、合规或安全建议。

### 2.2 External candidate reviewed and excluded

The buildingSMART Community Duplex Apartment file was reviewed because its repository describes it as a two-story dataset and licenses it under CC BY 4.0. It was not selected for the first held-out set because IfcOpenShell 0.8.5 on the frozen Windows/Python 3.13.15 environment terminated with access-violation exit code `-1073741819` while opening the downloaded IFC2X3 file. This was a local compatibility check only; no model call was made.

曾审核 buildingSMART Community 的 Duplex Apartment 文件，因为其仓库说明该数据为两层建筑，并采用 CC BY 4.0 许可证。该文件未被选为首版留出数据，是因为在冻结的 Windows/Python 3.13.15 环境中，IfcOpenShell 0.8.5 打开下载的 IFC2X3 文件时以访问冲突退出码 `-1073741819` 终止。这只是本地兼容性检查，没有发起模型调用。

References:

参考链接：

- [Community Sample Test Files repository and licensing notice](https://github.com/buildingsmart-community/Community-Sample-Test-Files)
  [Community Sample Test Files 仓库与许可说明](https://github.com/buildingsmart-community/Community-Sample-Test-Files)
- [Duplex Apartment dataset description](https://github.com/buildingsmart-community/Community-Sample-Test-Files/tree/main/IFC%202.3.0.1%20%28IFC%202x3%29/Duplex%20Apartment)
  [Duplex Apartment 数据集说明](https://github.com/buildingsmart-community/Community-Sample-Test-Files/tree/main/IFC%202.3.0.1%20%28IFC%202x3%29/Duplex%20Apartment)

This exclusion does not establish that the file is invalid or unusable in other environments. It establishes only that it is unsuitable for the first frozen Gate 4 path without changing the current runtime.

该排除决定并不说明该文件在其他环境中无效或不可用，只说明在不改变当前冻结运行环境的前提下，它不适合作为首版 Gate 4 路线。

## 3. Held-out IFC fixture

### 3.1 Dataset identity

- Dataset ID: `gate4-controlled-heldout-v0.1.0`.
  数据集 ID：`gate4-controlled-heldout-v0.1.0`。
- IFC schema: IFC4.
  IFC Schema：IFC4。
- Split: `held_out`.
  数据划分：`held_out`。
- Spatial structure: one site, one building, and exactly three explicit building storeys named `Ground Floor`, `Level 01`, and `Roof`.
  空间结构：一个场地、一个建筑，以及三个明确楼层，名称为 `Ground Floor`、`Level 01` 和 `Roof`。
- Element scope: at least 30 unchanged source elements distributed across `IfcBeam`, `IfcColumn`, `IfcWall`, and `IfcSlab`.
  构件范围：源模型中至少包含 30 个未变化构件，并分布于 `IfcBeam`、`IfcColumn`、`IfcWall` 和 `IfcSlab`。

All element names and tags must be neutral. They must not contain words such as `added`, `deleted`, `modified`, `held-out`, a question ID, or an expected answer.

所有构件名称与 Tag 必须保持中性，不得包含 `added`、`deleted`、`modified`、`held-out`、问题 ID 或预期答案等提示性文本。

### 3.2 Controlled change matrix

The revised model will contain exactly 12 scored changes. The design balances four change records per change type, four per entity type, and four per storey.

修订模型将恰好包含 12 条计分变更。设计在变化类型、实体类型和楼层三个维度上保持平衡：每种变化类型 4 条、每种实体类型 4 条、每个楼层 4 条。

| Entity type | Ground Floor | Level 01 | Roof |
|---|---|---|---|
| `IfcBeam` | added | deleted | property modified |
| `IfcColumn` | property modified | added | deleted |
| `IfcWall` | deleted | property modified | added |
| `IfcSlab` | added | deleted | property modified |

| 实体类型 | Ground Floor | Level 01 | Roof |
|---|---|---|---|
| `IfcBeam` | 新增 | 删除 | 属性修改 |
| `IfcColumn` | 属性修改 | 新增 | 删除 |
| `IfcWall` | 删除 | 属性修改 | 新增 |
| `IfcSlab` | 新增 | 删除 | 属性修改 |

The four property changes will use scalar values visible in the frozen Direct LLM model-pair summary:

四项属性修改将使用冻结的 Direct LLM 双版本摘要能够读取的标量值：

- `Pset_BeamCommon.LoadBearing`: `false` to `true`;
  `false` 变为 `true`；
- `Pset_ColumnCommon.IsExternal`: `true` to `false`;
  `true` 变为 `false`；
- `Pset_WallCommon.FireRating`: `"60"` to `"90"`;
  `"60"` 变为 `"90"`；
- `Pset_SlabCommon.LoadBearing`: `false` to `true`.
  `false` 变为 `true`。

The source model will also contain unchanged look-alike elements with the same entity types, storeys, and property sets. These are static distractors. There must be no unrecorded source-to-revised differences.

源模型还将包含在实体类型、楼层和属性集上相似但保持不变的构件，作为静态干扰项。源模型与修订模型之间不得存在任何未记录差异。

### 3.3 Frozen type boundary

The primary scored set is limited to `added`, `deleted`, and `property_modified`. Geometry and relationship changes are excluded because the frozen `change-record.schema.json` does not represent them, the frozen query contract only treats `geometry_modified` as a negative-control vocabulary item, and the Direct LLM summary excludes geometry and relationships.

主计分集仅包含 `added`、`deleted` 和 `property_modified`。几何与关系变化被排除，是因为冻结的 `change-record.schema.json` 无法表达它们，冻结的查询契约只把 `geometry_modified` 作为负控词汇，而且 Direct LLM 摘要不包含几何与关系信息。

Multi-storey context is therefore the selected Gate 4 coverage expansion. Geometry or relationship feasibility may be studied later as a separately declared extension, but it must not be mixed into this frozen three-workflow comparison.

因此，Gate 4 本轮选择以多楼层语境作为覆盖扩展。几何或关系变化可以在后续作为单独声明的扩展研究，但不得混入本次冻结的三工作流对比。

## 4. Deterministic ground truth

The Gate 4 generator must use fixed GlobalIds, fixed neutral names and tags, fixed property values, normalized owner-history timestamps, and deterministic serialization. Two clean generations must produce byte-identical source and revised IFC files.

Gate 4 生成器必须使用固定 GlobalId、固定中性名称与 Tag、固定属性值、规范化 OwnerHistory 时间戳以及确定性序列化。两次干净生成必须产生字节完全一致的源 IFC 与修订 IFC。

Ground truth will be emitted as schema version `0.1.0` Change Records that validate against the frozen `schemas/change-record.schema.json`. The generator operation ledger is authoritative for intended changes; IfcDiff 0.8.5 with explicit property comparison is an independent detector used to confirm the exact added, deleted, and property-modified sets.

真值将以 Schema 版本 `0.1.0` 的 Change Record 输出，并通过冻结的 `schemas/change-record.schema.json` 校验。生成器操作账本是预期变更的权威来源；启用明确属性比较配置的 IfcDiff 0.8.5 作为独立检测器，用于确认精确的新增、删除与属性修改集合。

Before question generation, an offline verifier must pass all of the following checks:

在生成问题前，离线验证器必须通过以下全部检查：

1. source and revised IFC SHA-256 hashes are recorded;
   已记录源 IFC 与修订 IFC 的 SHA-256；
2. both IFC files open successfully in the frozen environment;
   两个 IFC 文件均能在冻结环境中成功打开；
3. IFC schema, storey names, element counts, and GlobalId uniqueness are valid;
   IFC Schema、楼层名称、构件数量与 GlobalId 唯一性均有效；
4. every Change Record validates against the frozen Schema;
   每条 Change Record 均通过冻结 Schema 校验；
5. every added and deleted entity is present on exactly the correct side;
   每个新增与删除实体仅出现在正确版本一侧；
6. every old and new property value matches the two IFC files;
   每个属性旧值与新值均与两个 IFC 文件一致；
7. every storey is supported by an explicit IFC spatial relationship rather than inference;
   每个楼层均由明确的 IFC 空间关系支持，而不是推断；
8. IfcDiff returns exactly the 12 expected changes and no extras;
   IfcDiff 恰好返回 12 条预期变更且无额外项；
9. two clean generations are byte-identical;
   两次干净生成结果字节完全一致；
10. the Direct LLM input contains two inventories and no precomputed difference or reference answer.
    Direct LLM 输入仅包含两个版本清单，不含预计算差异或参考答案。

Reference answers will be generated deterministically by applying each frozen structured selection to the held-out Change Records. A reference self-score of `1.0` is only a harness check and must never be reported as model performance.

参考答案将通过把每个冻结的结构化筛选条件确定性应用于留出 Change Record 来生成。参考答案自评分为 `1.0` 仅用于检查评测工具接线，不得表述为模型表现。

## 5. Held-out question set

### 5.1 Size and language

The first Gate 4 set will contain exactly 40 English questions. English is retained as the evaluation language so that question language does not become an additional experimental variable. Public documentation of the design and results remains English-first with paragraph-by-paragraph Simplified Chinese.

首版 Gate 4 将包含恰好 40 个英文问题。评测继续使用英语，避免问题语言成为额外实验变量。公开的设计与结果文档继续采用英语为主、简体中文逐段对照。

Because the frozen evaluation-question Schema requires question IDs matching `^gate3-q[0-9]{2}-`, held-out IDs will continue from `gate3-q09-...` through `gate3-q48-...`. This naming is a frozen-contract compatibility artifact; the file split and dataset ID remain `held_out` and Gate 4 specific.

由于冻结的 evaluation-question Schema 要求问题 ID 匹配 `^gate3-q[0-9]{2}-`，留出问题将从 `gate3-q09-...` 延续至 `gate3-q48-...`。该命名只是冻结契约的兼容性产物；文件的数据划分与数据集 ID 仍明确属于 `held_out` 和 Gate 4。

### 5.2 Category allocation

| Frozen category | Count | Intended status |
|---|---:|---|
| `summary` | 4 | `answered` |
| `fact_lookup` | 6 | `answered` |
| `filtered_lookup` | 14 | `answered` |
| `property_change` | 6 | `answered` |
| `negative_control` | 5 | `not_found` |
| `evidence_boundary` | 5 | `insufficient_evidence` |
| **Total** | **40** | 30 answered, 5 not found, 5 insufficient evidence |

| 冻结类别 | 数量 | 预期状态 |
|---|---:|---|
| `summary` | 4 | `answered` |
| `fact_lookup` | 6 | `answered` |
| `filtered_lookup` | 14 | `answered` |
| `property_change` | 6 | `answered` |
| `negative_control` | 5 | `not_found` |
| `evidence_boundary` | 5 | `insufficient_evidence` |
| **合计** | **40** | 30 个已回答、5 个未发现、5 个证据不足 |

Positive questions must collectively exercise every change type, entity type, storey, and property field. Every one of the 12 Change Records must be a target in at least two non-summary questions and must also appear in at least one summary question.

正例问题必须整体覆盖每种变化类型、实体类型、楼层与属性字段。12 条 Change Record 中的每一条都必须至少成为两个非摘要问题的目标，并至少出现在一个摘要问题中。

Filtered questions must include single-filter and multi-filter cases, including change type plus entity type, entity type plus storey, and change type plus entity type plus storey. The structured selection remains a conjunction of the frozen fields; the question must not require unsupported sorting, arithmetic, geometry, causal inference, or open-ended engineering judgment.

筛选问题必须同时包含单条件与多条件情况，包括变化类型加实体类型、实体类型加楼层，以及变化类型加实体类型加楼层。结构化筛选继续对冻结字段执行合取逻辑；问题不得要求契约不支持的排序、计算、几何、因果推断或开放式工程判断。

Negative controls will cover verified absence of geometry changes, a valid but absent entity/storey combination, and at least one well-formed nonexistent GlobalId. Evidence-boundary questions will ask about safety, compliance, causal responsibility, or coordination priority that the Change Records cannot establish.

负控问题将覆盖经验证不存在的几何变化、合法但不存在的实体与楼层组合，以及至少一个格式合法但不存在的 GlobalId。证据边界问题将询问 Change Record 无法支持的安全、合规、因果责任或协调优先级结论。

No question or reference answer may contain an unsupported structural-safety conclusion. The correct response to a safety-boundary question must state the verified revision fact and the missing evidence or required qualified assessment.

任何问题或参考答案都不得包含无证据支持的结构安全结论。安全边界问题的正确回答必须同时说明已验证的版本变更事实，以及仍缺少的证据或所需的专业评估。

### 5.3 Anti-leakage checks

Before freezing the question set, an offline checker must confirm unique IDs, Schema validity, `split: held_out`, no exact normalized-text match with the eight development questions, no development-only GlobalId, no answer-bearing words in element names or tags, and no reference-answer content in either workflow input.

冻结问题集前，离线检查器必须确认：ID 唯一、Schema 有效、`split: held_out`、与八个开发问题不存在规范化后的逐字匹配、不包含开发集专用 GlobalId、构件名称或 Tag 不泄露答案，并且任何工作流输入中都不包含参考答案内容。

## 6. Repeated-run protocol

Each of the 40 questions will be run three times under each of the three frozen workflows, producing 360 primary workflow executions. Proposed validator and bounded repair calls are auxiliary calls and must be counted separately in usage, latency, and cost reporting.

40 个问题将在三个冻结工作流下各重复运行三次，共产生 360 次主工作流执行。Proposed 的 Validator 与受控修复属于辅助调用，必须在用量、延迟和成本报告中单独计数。

The locked model configuration remains DeepSeek `deepseek-v4-flash`, reasoning effort `high`, maximum answer output 16,000 tokens, `store: false`, at most two transient retries, no answer repair for Direct LLM or Tool-Using Agent, and at most one controlled repair for Proposed. The API exposes no fixed seed, so the runs must not be described as deterministic sampling.

锁定的模型配置继续为 DeepSeek `deepseek-v4-flash`、reasoning effort `high`、回答输出上限 16,000 tokens、`store: false`、瞬态错误最多重试两次、Direct LLM 与 Tool-Using Agent 不修复答案、Proposed 最多进行一次受控修复。由于 API 不提供固定 seed，不得把重复运行表述为确定性采样。

Execution will use three complete repetition blocks. Workflow order will rotate to reduce systematic provider-time bias:

执行采用三个完整重复区组，并轮换工作流顺序以降低提供商时间漂移造成的系统偏差：

1. repetition 1: Direct LLM, Tool-Using Agent, Proposed;
   第一次重复：Direct LLM、Tool-Using Agent、Proposed；
2. repetition 2: Tool-Using Agent, Proposed, Direct LLM;
   第二次重复：Tool-Using Agent、Proposed、Direct LLM；
3. repetition 3: Proposed, Direct LLM, Tool-Using Agent.
   第三次重复：Proposed、Direct LLM、Tool-Using Agent。

The exact question order within every block will be fixed in a pre-generated schedule and hashed before calls. Failed infrastructure attempts may continue from checkpoints under the same configuration. A non-empty but Schema-invalid or factually wrong response is an experimental failure, not an infrastructure retry.

每个区组内的准确问题顺序将在调用前由预生成计划固定并计算哈希。基础设施失败可以在相同配置下从检查点续跑。非空但 Schema 非法或事实错误的响应属于实验失败，而不是基础设施重试。

The provisional total cost ceiling is USD 0.75. The ceiling includes all retained primary calls, validators, repairs, and transient retries. If the ceiling is reached, execution stops without changing prompts or excluding difficult questions. The incomplete block is reported and continued only under the identical frozen configuration after explicit review.

临时总费用硬上限为 0.75 美元。该上限包含所有保留的主调用、Validator、修复与瞬态重试。达到上限后必须停止执行，不得修改提示词或排除困难问题。未完成区组应如实报告，且只有在明确审核后才能用完全相同的冻结配置续跑。

## 7. Metrics and uncertainty

The frozen per-answer scorer remains authoritative for Schema compliance, status accuracy, semantic exact match, change precision/recall/F1, deterministic evidence-support rate, and status consistency. Gate 4 aggregation may add reporting code, but it may not redefine any per-answer identity or score.

冻结的逐答案评分器继续作为以下指标的权威实现：Schema 合规、状态准确率、语义精确匹配、变更 Precision/Recall/F1、确定性证据支持率以及状态一致性。Gate 4 可以增加汇总代码，但不得重新定义任何逐答案事实身份或评分。

Gate 4 will additionally report completion rate, Proposed repair rate, unsupported or indeterminate claim rate, latency, estimated cost, transient retry count, and failure-category distribution.

Gate 4 还将报告运行完成率、Proposed 修复率、unsupported 或 indeterminate 声明率、延迟、估算成本、瞬态重试次数与失败类型分布。

For each workflow, aggregate metrics will be reported per repetition and across all three repetitions using the mean, sample standard deviation, and minimum-to-maximum range. Pairwise workflow differences will use a question-clustered paired bootstrap with 2,000 resamples and fixed analysis seed `20260808`; all repetitions for a sampled question stay in the same bootstrap cluster. This uncertainty analysis changes only aggregation, not frozen scoring.

每个工作流的汇总指标将分别按重复次数报告，并在三次重复上报告均值、样本标准差与最小值至最大值范围。工作流两两差异将采用以问题为聚类单位的配对 Bootstrap，进行 2,000 次重采样，并固定分析 seed 为 `20260808`；同一问题的全部重复结果始终位于同一个 Bootstrap 聚类中。该不确定性分析只影响汇总，不改变冻结评分。

Results will also report per-category metrics and each question's success frequency from zero to three. No significance claim will be made solely from a confidence interval, and no result will be generalized beyond this controlled held-out fixture.

结果还将按问题类别报告指标，并报告每个问题在三次重复中的成功次数（0 至 3）。不得仅凭置信区间作出显著性结论，也不得把结果推广到该受控留出样例之外。

## 8. Manual audit

### 8.1 Pre-run audit

Before the specification and artifacts are frozen, one human reviewer will inspect all 12 Change Records and all 40 questions. The reviewer will use a checklist covering IFC evidence, location support, old/new values, question-selection alignment, answerability, wording independence, safety boundaries, licensing, and absence of personal or sensitive information.

在规格与产物冻结前，由一名人工审核者检查全部 12 条 Change Record 与 40 个问题。审核清单覆盖 IFC 证据、位置支持、属性旧值与新值、问题与筛选条件对齐、可回答性、措辞独立性、安全边界、许可证，以及是否不存在个人或敏感信息。

Because there is only one reviewer, the report will not claim inter-rater agreement. Any correction made before freeze is recorded as specification drafting, not as a post-result tuning decision.

由于只有一名审核者，报告不会声称评审者间一致性。冻结前发生的修正应记录为规格起草过程，而不是查看结果后的调优决定。

### 8.2 Post-run audit

The post-run audit will inspect all 45 evidence-boundary executions (`5 questions × 3 workflows × 3 repetitions`) and a preselected stratified sample of 10 additional question IDs covering every remaining category. All nine executions for each sampled question will be audited, producing 135 audited answers in total.

运行后的人工审核将检查全部 45 个证据边界执行结果（`5 个问题 × 3 个工作流 × 3 次重复`），并预先分层抽取另外 10 个问题 ID，覆盖其余所有类别。每个抽中问题的九个执行结果全部审核，因此总计人工审核 135 个答案。

Workflow and repetition labels will be replaced by neutral codes during review. For each answer, the reviewer will label atomic claims as `supported`, `unsupported`, or `indeterminate`, verify evidence references, record any safety overreach, and assign one or more frozen failure categories where applicable. The mapping from neutral codes to workflows will be revealed only after audit labels are saved.

审核时将用中性代码替换工作流与重复次数标签。审核者需要把每个答案中的原子声明标为 `supported`、`unsupported` 或 `indeterminate`，核对证据引用，记录任何安全越界，并在适用时分配一个或多个冻结失败类别。只有在审核标签保存后，才揭示中性代码与工作流的映射。

## 9. Pre-call freeze manifest

No model call is allowed until an offline freeze manifest records and verifies all of the following:

在离线冻结清单记录并核验以下全部内容前，不得发起模型调用：

- Gate 3 baseline commit `abcb095` and the current Gate 4 implementation commit;
  Gate 3 基线提交 `abcb095` 与当前 Gate 4 实现提交；
- this specification's SHA-256 and frozen-review status;
  本规格的 SHA-256 与冻结审核状态；
- source and revised IFC paths and SHA-256 hashes;
  源 IFC、修订 IFC 的路径与 SHA-256；
- Change Record, question, reference-answer, and Direct-input hashes;
  Change Record、问题、参考答案与 Direct 输入的哈希；
- frozen prompt/module hashes or an exact clean-tree comparison to `abcb095` for every protected Gate 3 file;
  所有受保护 Gate 3 文件的提示词或模块哈希，或与 `abcb095` 的精确干净工作树比较；
- model configuration, repetition count, workflow order, question schedule, budget, and stop rules;
  模型配置、重复次数、工作流顺序、问题计划、预算与停止规则；
- passing offline tests for generation, verification, query behavior, scoring, evidence validation, and a Gate 3 regression replay;
  生成、验证、查询行为、评分、证据验证与 Gate 3 回归重放的全部离线测试通过；
- confirmation that no API key or model output is present in the freeze artifacts.
  确认冻结产物中不存在 API Key 或模型输出。

The manifest hash and implementation commit must be recorded in GitHub Issue `#3` before the first paid call.

首次付费调用前，必须把冻结清单哈希与实现提交记录到 GitHub Issue `#3`。

## 10. Amendment and stopping rules

Before freeze, this specification could change during human review. Now that it is frozen, any unavoidable implementation correction must be documented in Issue `#3` before rerunning every affected workflow, question, and repetition. The correction may restore the specified behavior but may not optimize against observed held-out results.

冻结前，本规格可以在人工审核期间修改。现已冻结，任何无法避免的实现修正都必须先在 Issue `#3` 中记录，再重新运行所有受影响的工作流、问题与重复。修正只能恢复规格规定的行为，不得针对已观察的留出结果进行优化。

The evaluation stops and requests review if protected Gate 3 files differ from `abcb095`, the offline verifier finds an unrecorded IFC difference, reference answers become available to a model input, the cost ceiling is reached, or provider behavior prevents the locked configuration from being executed.

若受保护的 Gate 3 文件与 `abcb095` 不同、离线验证器发现未记录的 IFC 差异、参考答案进入模型输入、费用达到硬上限，或提供商行为导致锁定配置无法执行，评测必须停止并请求审核。

## 11. Reporting boundary

Until the held-out evaluation is complete, Gate 3 figures remain preliminary development findings. Gate 4 results must be described as repeated results on one independently constructed controlled held-out fixture, with explicit limitations for synthetic data, three repetitions, one model provider, and the frozen change-type boundary.

在留出评测完成前，Gate 3 数字继续只能表述为 preliminary development findings。Gate 4 结果必须表述为在一个独立构造的受控留出样例上的重复实验结果，并明确说明合成数据、三次重复、单一模型提供商以及冻结变化类型边界等限制。

Public documentation, Issue updates, and later release notes must remain English-first with paragraph-by-paragraph Simplified Chinese. When a paired list item shares the same Gate number, path, label, or bullet structure, write that identifier once in English and place the Chinese translation on the next indented line without repeating the identifier. They must not disclose personal information or any private intended use of the project.

公开文档、Issue 更新与后续发布说明必须继续采用英语为主、简体中文逐段对照。当成对列表项共享相同的 Gate 编号、路径、标签或项目符号结构时，只在英文行呈现一次标识，中文译文在下一缩进行直接写内容，不重复相同标识。所有公开内容均不得泄露个人信息或项目的任何私人预期用途。
