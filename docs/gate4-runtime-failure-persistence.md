# Gate 4 runtime failure-persistence amendment

## Status

This amendment is implemented and verified locally but is not yet approved for public merge or renewed paid execution. Gate 4 paid calls remain paused after primary execution 78 of 360.

本修订已在本地实现并验证，但尚未获准公开合并或重新开始付费执行。Gate 4 付费调用目前停在 360 次主执行中的第 78 次之后。

## Trigger and evidence boundary

The frozen runner correctly treated non-empty but Schema-invalid model output as an experimental failure rather than an infrastructure retry. The Gate 4 wrapper nevertheless terminated the whole process before it could retain the raw response, exact usage, and failure record. Four such failures were observed at executions 50, 72, 73, and 78. No reference answers were read and no held-out answers were scored or used to change prompts, Schemas, workflow logic, or scoring rules.

冻结运行器正确地把非空但 Schema 非法的模型输出视为实验失败，而不是基础设施重试；但 Gate 4 外壳会在保存原始响应、精确用量和失败记录前终止整个进程。执行 50、72、73 和 78 共观察到四次此类失败。期间没有读取参考答案，也没有对留出答案进行评分或据此修改提示词、Schema、工作流逻辑或评分规则。

The first paid attempt also returned before the sandbox denied creation of the result directory. That response and the four pre-amendment Schema failures lack checkpointed token metadata. The frozen CNY 2.50 contingency reserve covers these unmetered attempts. The last checkpointed conservative estimate is CNY 1.46357, so any reviewed continuation must start with provider-attributed spend of at least CNY 3.96357 unless a higher provider debit is available.

第一次付费尝试返回后，沙箱拒绝创建结果目录，因此该响应与修订前的四次 Schema 失败都没有保存 token 元数据。冻结的 CNY 2.50 应急储备用于覆盖这些未计量尝试。最后一次 checkpoint 的保守估算为 CNY 1.46357，因此通过审核后的续跑必须至少以 CNY 3.96357 作为提供商归因费用起点；若提供商显示更高扣费，则使用更高值。

## Amendment

Only the new Gate 4 wrapper is changed. The wrapper now keeps an in-memory journal of every successful provider response for the current primary execution. If later parsing or Schema validation identifies a model-output failure, it writes the raw provider responses, exact cumulative usage, failure category, and a no-retry decision before advancing the checkpoint.

本修订只修改新增的 Gate 4 外壳。外壳现在会为当前主执行在内存中记录每个成功返回的提供商响应。如果后续解析或 Schema 验证识别出模型输出失败，外壳会先保存原始提供商响应、精确累计用量、失败类别和不重试决定，再推进 checkpoint。

The amendment distinguishes model-output failures from infrastructure failures. Schema/output-format, parameter-generation, and tool-selection failures are retained as experimental failures without retry. A provider call that raises before returning a response, including exhausted network retries, remains fatal and does not advance the checkpoint.

本修订区分模型输出失败与基础设施失败。Schema/输出格式、参数生成和工具选择失败会作为实验失败保留且不重试。若提供商调用在返回响应前抛出异常，包括网络重试耗尽，进程仍会停止且不会推进 checkpoint。

## Frozen compatibility

The 37 protected Gate 3 files must remain byte-identical to commit `abcb095858ea45a1727d68d91063376ef77381ad`. The question set, schedule, audit selection, pre-run audit, review state, final manifest, model configuration, prompts, Schemas, workflow logic, scoring rules, repetition order, exclusions, and budget thresholds remain unchanged.

37 个受保护 Gate 3 文件必须继续与提交 `abcb095858ea45a1727d68d91063376ef77381ad` 字节一致。问题集、调度、盲审选择、运行前审核、审核状态、最终清单、模型配置、提示词、Schema、工作流逻辑、评分规则、重复顺序、排除规则和预算阈值均保持不变。

The 74 valid candidates already retained through execution 78 are not affected by the missing failure-persistence branch. The four pre-amendment failures remain failures and are not retried; their manually retained records explicitly state that raw responses and token metadata were unavailable after process termination. A reviewed continuation begins at execution 79.

截至执行 78 已保留的 74 个有效候选不受缺失的失败持久化分支影响。修订前的四次失败继续作为失败保留且不得重试；其人工保留记录明确说明进程终止后无法取得原始响应和 token 元数据。通过审核后的续跑从执行 79 开始。

## Verification and authorization boundary

Offline tests must prove that raw responses and exact usage are persisted, model-output failures advance once without retry, and infrastructure failures remain fatal. Foundation guard and the protected Gate 3 byte comparison must pass. No paid call may continue until the amendment is reviewed, publicly recorded, merged, and followed by a renewed exact live-call authorization.

离线测试必须证明：原始响应和精确用量能够保存；模型输出失败只推进一次且不重试；基础设施失败仍会导致停止。foundation guard 与受保护 Gate 3 字节比较必须通过。在本修订完成审核、公开记录、合并并再次获得精确实时调用授权前，不得恢复任何付费调用。
