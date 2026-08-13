# Gate 3 Development Results / Gate 3 开发集结果

## Scope / 范围

This note reports a preliminary development-set comparison of three BIM revision-analysis workflows. It checks whether the evaluation harness and evidence chain behave as intended; it is not a held-out benchmark or a claim of general model performance.

本文记录三种 BIM 版本分析工作流在开发集上的初步对比，用于检查评测框架与证据链是否按预期工作；它不是独立留出基准，也不代表模型的通用性能。

All retained runs used DeepSeek V4 Flash through a Responses-compatible API, `high` reasoning effort, a 16,000-token answer-generation limit, the same eight development questions, and one retained answer per question and condition.

所有保留运行均通过 Responses 兼容 API 使用 DeepSeek V4 Flash，推理强度为 `high`，答案生成上限为 16,000 tokens；三种条件采用相同的八道开发问题，每个问题与条件保留一次最终答案。

## Results / 结果

| Workflow / 工作流 | Completion / 完成率 | Status accuracy / 状态准确率 | Exact match / 精确匹配 | Change F1 / 变更 F1 | Evidence support / 证据支持率 | Retained API cost / 保留运行成本 |
|---|---:|---:|---:|---:|---:|---:|
| Direct LLM | 100% | 87.5% | 37.5% | 0.600 | 0.700 | $0.005284 |
| Tool-Using Agent | 100% | 100% | 87.5% | 0.947 | 1.000 | $0.004043 |
| Proposed | 100% | 100% | 100% | 1.000 | 1.000 | $0.018093 |

The Direct condition identified some changes correctly but was less reliable on modified-property facts, negative-evidence boundaries, and evidence citations. Deterministic Change Record access substantially improved fact recovery and evidence support on this development set.

Direct 条件能够正确识别部分变更，但在属性修改事实、否定证据边界与证据引用方面可靠性较低。在本开发集上，访问确定性的 Change Record 明显提升了事实恢复与证据支持。

The Proposed workflow added candidate-Schema validation, exact coverage of the model-selected Change Record query result, and atomic free-text claim classification. Two questions used their single permitted repair. All eight final Proposed answers had complete tool-result coverage and a final claim verdict of `pass`.

Proposed 工作流增加了候选 Schema 验证、对模型所选 Change Record 查询结果的精确覆盖检查，以及自由文本原子声明分类。其中两道问题使用了唯一一次允许的修复；最终八道答案均完整覆盖工具结果，声明判定均为 `pass`。

The total estimated cost of the retained final runs was USD 0.027420. Discarded diagnostic attempts are excluded.

保留的最终运行估算总成本为 0.027420 美元，不包含调试过程中舍弃的诊断尝试。

## Development Findings / 开发阶段发现

- DeepSeek thinking mode rejected forced `tool_choice`; the runner now exposes one tool, requests a call in the instruction, and verifies exactly one call in the host.<br>
  DeepSeek thinking 模式不接受强制 `tool_choice`；当前运行器只暴露一个工具，在指令中要求调用，并由宿主验证调用次数恰好为一次。
- Unrestricted change-type strings allowed case errors to look like empty results; the query contract now uses a fixed lowercase vocabulary.<br>
  不受限制的变更类型字符串会让大小写错误伪装成空结果；查询契约现已使用固定的小写词表。
- Long reasoning sometimes exhausted short output limits; all answer conditions now share a 16,000-token limit.<br>
  长推理有时会耗尽较短输出限额；目前所有答案条件统一使用 16,000-token 上限。
- Provider-success responses can still contain empty structured output; these are retried at most twice and recorded in usage.<br>
  提供方返回成功时仍可能出现空的结构化输出；此类情况最多重试两次，并记录在使用量中。
- Long local runs checkpoint per question and continue under the same cumulative budget.<br>
  较长的本地运行按问题保存检查点，并在同一累计预算约束下恢复。

## Limitations / 局限

- The questions and workflow contracts were iteratively refined using this development set, so the results are vulnerable to development-set overfitting.<br>
  问题与工作流契约使用同一开发集反复调整，因此结果存在开发集过拟合风险。
- Each final question-condition pair has one retained answer; there is no variance estimate or confidence interval.<br>
  每个问题与条件仅保留一次最终答案，目前没有方差估计或置信区间。
- The same model provider performs generation and Proposed free-text validation. Deterministic evidence and coverage checks are independent, but the claim verdict is not human ground truth.<br>
  生成与 Proposed 自由文本验证使用同一模型提供方。确定性证据及覆盖检查相对独立，但声明判定并非人工真值。
- The controlled data contain only three Change Records and do not validate larger projects, multiple IFC schemas, geometry changes, or relationship changes.<br>
  受控数据仅包含三条 Change Record，尚未验证更大项目、多种 IFC Schema、几何变更或关系变更。
- The cost table covers retained final runs only; discarded diagnostic attempts are not included.<br>
  成本表仅覆盖保留的最终运行，不包含舍弃的诊断尝试。

The next evaluation step is to freeze the current contracts, create a separate held-out revision set and questions, and run repeated comparisons without modifying prompts based on held-out outcomes.

下一评测步骤是冻结当前契约，建立独立的留出版本与问题集，并在不根据留出结果修改提示词的前提下执行重复对比。
