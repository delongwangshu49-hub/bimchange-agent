# Gate 4 Pre-Call Orchestration and Freeze

# Gate 4 调用前编排与冻结

## Status

The single-human pre-run review, Issue `#3` freeze record, and PR `#8` review and merge are complete. Their deterministic state transition is recorded in `configs/gate4-precall-review-state.json`. This does not authorize model or paid API calls. No Gate 4 model output, post-run audit, or post-run result has been generated.

  单人运行前审核、Issue `#3` 冻结记录以及 PR `#8` 审核与合并均已完成，其确定性状态转换记录在 `configs/gate4-precall-review-state.json` 中。本文不授权模型或付费 API 调用，尚未生成任何 Gate 4 模型输出、运行后审核或运行后结果。

The protected Gate 3 prompt, Schema, question-level workflow logic, evidence validation, and scoring remain byte-identical to commit `abcb095858ea45a1727d68d91063376ef77381ad`.

  受保护的 Gate 3 提示词、Schema、逐问题工作流逻辑、证据验证与评分代码继续与提交 `abcb095858ea45a1727d68d91063376ef77381ad` 保持字节一致。

## Review-state transition

The transition record binds the approved review decision to PR `#8`, merge commit `4b38318bb58db39915717294bc3cc9feb5eeedd4`, and the two public Issue `#3` records. It also preserves the SHA-256 lineage of the earlier pending-review audit and manifest.

  状态转换记录把已批准的审核结论绑定到 PR `#8`、合并提交 `4b38318bb58db39915717294bc3cc9feb5eeedd4` 及两条公开 Issue `#3` 记录，并保留此前待审核 audit 与 manifest 的 SHA-256 沿革。

The generator deterministically marks the nine checklist items, 12 Change Record rows, and 40 question rows complete. The resulting manifest marks only the three completed non-call gates as `COMPLETE`; `separate_live_call_authorization` remains `PENDING`, and `live_calls_authorized` remains `false`.

  生成器会确定性地把 9 个清单项、12 条 Change Record 记录与 40 道问题记录转换为完成状态。生成后的 manifest 仅把三个已完成的非调用门标记为 `COMPLETE`；`separate_live_call_authorization` 继续为 `PENDING`，`live_calls_authorized` 继续为 `false`。

## Deterministic primary schedule

The schedule contains exactly 360 primary executions: 40 held-out questions × 3 workflows × 3 complete repetition blocks. Auxiliary Proposed validator and controlled repair calls are excluded from the primary count and will be reported separately.

  调度恰好包含 360 次主执行，即 40 道留出问题 × 3 个工作流 × 3 个完整重复区组。Proposed 的 Validator 与受控修复属于辅助调用，不计入主执行数量，后续将单独报告。

- Repetition 1: Direct LLM, Tool-Using Agent, Proposed.
  第一次重复依次运行 Direct LLM、Tool-Using Agent 与 Proposed。
- Repetition 2: Tool-Using Agent, Proposed, Direct LLM.
  第二次重复依次运行 Tool-Using Agent、Proposed 与 Direct LLM。
- Repetition 3: Proposed, Direct LLM, Tool-Using Agent.
  第三次重复依次运行 Proposed、Direct LLM 与 Tool-Using Agent。

Each block's exact 40-question order is derived by SHA-256 ranking from the fixed seed `gate4-question-order-20260808-v1`. The complete execution list and per-block question-order hashes are stored in `evals/schedules/held_out/gate4-run-schedule.json`. The whole-file hash is recorded by the pre-run audit and freeze manifest.

  每个区组内 40 道问题的精确顺序由固定 seed `gate4-question-order-20260808-v1` 通过 SHA-256 排序确定。完整执行列表与每个区组的问题顺序哈希保存在 `evals/schedules/held_out/gate4-run-schedule.json`，整文件哈希由运行前审核与冻结清单记录。

## Preselected blinded audit sample

The post-run manual audit selection is frozen before any output exists. It includes all five `evidence_boundary` question IDs and ten additional IDs selected as two per remaining category: `summary`, `fact_lookup`, `filtered_lookup`, `property_change`, and `negative_control`.

  运行后人工审核样本在任何模型输出产生前冻结。样本包含全部 5 道 `evidence_boundary` 问题，以及从其余类别各预选 2 道、合计 10 道附加问题，覆盖 `summary`、`fact_lookup`、`filtered_lookup`、`property_change` 与 `negative_control`。

All nine workflow/repetition executions for each of the 15 selected question IDs will be audited, for 135 answers in total. The later review bundle will replace workflow and repetition labels with neutral codes `A001`–`A135`; the mapping must remain hidden from the reviewer until every label is saved. No post-run audit artifact is created at this stage.

  15 道入选问题的每一道都审核其 9 个工作流与重复组合，共审核 135 个答案。后续审核包将使用中性代码 `A001`–`A135` 替换工作流与重复标签，并在全部审核标签保存前向审核者隐藏映射。本阶段不会创建运行后审核产物。

## Budget amendment and stop rules

The provisional USD 0.75 ceiling is superseded before any Gate 4 model call. The sole evaluation-wide hard ceiling is CNY 25.00.

  在任何 Gate 4 模型调用前，暂定的 0.75 美元上限已被替代。整个评测唯一的费用硬上限为人民币 25.00 元。

Automated enforcement uses the frozen Gate 3 USD-per-million-token rates with a deliberately conservative conversion of CNY 10.00 per USD. It stops at an internal USD 2.25 / CNY 22.50 estimate and reserves CNY 2.50 for provider reporting lag or charged failed attempts without usable token metadata.

  自动阻断继续使用冻结的 Gate 3 每百万 token 美元费率，并采用每美元人民币 10.00 元的保守换算。内部估算达到 2.25 美元或人民币 22.50 元即停止，并预留人民币 2.50 元，以覆盖提供商账单延迟或缺少可用 token 元数据但仍被计费的失败请求。

The authoritative spend is the greater of attributable provider debit in CNY and the conservative token estimate. Primary calls, validators, repairs, transient retries, and any charged failed attempt are all in scope. A request is blocked before sending if the projection can reach a threshold. An incomplete block is retained and may resume only after explicit review with the identical frozen configuration.

  权威费用口径取可归因的提供商人民币扣费与保守 token 估算中的较大值。主调用、Validator、修复、瞬态重试以及任何被计费的失败请求全部计入。若下一请求的预测费用可能触及阈值，则在发送前阻断。未完成区组必须保留，且只能在明确审核后使用完全相同的冻结配置续跑。

## Frozen-function staging

The new `scripts/run_gate4_workflows.py` wrapper does not edit Gate 3 code. Before reading held-out inputs it runs the foundation guard and reproduces four retained Gate 3 development artifacts in an isolated Git archive while rerunning the positive, negative, candidate-contract, query, workflow dry-run, and summary checks.

  新增的 `scripts/run_gate4_workflows.py` 外壳不修改 Gate 3 代码。在读取留出输入前，它先运行 foundation guard，并在隔离的 Git 快照中复现四项保留的 Gate 3 开发产物，同时重跑正例、负例、候选契约、查询、工作流 dry-run 与汇总检查。

After that replay passes, the wrapper creates a temporary staging directory. Byte-frozen Gate 3 modules and Schemas are copied there, while the logical held-out question, Change Record, and Direct-input artifacts are mapped to the fixed runtime paths required by the frozen functions. Reference answers are never staged. Public development files are never overwritten.

  该回放通过后，外壳才建立临时暂存目录。字节冻结的 Gate 3 模块与 Schema 被复制到其中，逻辑上的留出问题、Change Record 与 Direct 输入则映射到冻结函数要求的固定运行时路径。参考答案绝不进入暂存环境，公开开发文件也绝不会被覆盖。

## Authorization boundary

The wrapper defaults to an offline dry run. It validates the completed public freeze while requiring `separate_live_call_authorization: PENDING` and `live_calls_authorized: false`. Live execution additionally requires a clean reviewed worktree, the `--live` switch, and the exact separate authorization phrase supplied at run time. Approval checks execute before any local key is read.

  外壳默认只运行离线 dry-run，并在要求 `separate_live_call_authorization: PENDING` 与 `live_calls_authorized: false` 的同时验证已完成的公开冻结。正式执行还必须满足工作树干净且已审核、显式提供 `--live` 开关，以及在运行时提供精确的单独授权短语。批准检查始终先于任何本地密钥读取。

## Offline commands

```powershell
.\.venv\Scripts\python.exe scripts\generate_gate4_freeze_artifacts.py
.\.venv\Scripts\python.exe scripts\verify_gate4_freeze.py
.\.venv\Scripts\python.exe scripts\test_gate4_freeze.py
.\.venv\Scripts\python.exe scripts\run_gate4_workflows.py
```

These commands do not make a model call. The freeze manifest is generated only after the implementation files, schedule, and pre-run audit have a local implementation commit, so the manifest can record that exact commit without a self-reference.

  这些命令不会发起模型调用。冻结清单只在实现文件、调度与运行前审核形成一个本地实现提交后生成，因此清单可以记录该精确提交而不产生自引用。
