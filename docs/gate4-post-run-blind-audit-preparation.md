# Gate 4 post-run blind-audit preparation

The 360 frozen primary executions are complete. Before any scoring or workflow comparison, the retained result files are hashed and the preselected 135-answer manual-audit packet is generated offline.

Gate 4 的 360 次冻结主执行已经完成。在进行任何评分或工作流对比前，先离线冻结保留结果文件的哈希，并生成预选的 135 答案人工盲审包。

The packet contains all nine executions for each of the 15 question IDs selected before model calls. Neutral codes `A001` through `A135` replace execution, workflow, and repetition identities. Candidate-unavailable experimental failures remain visible as neutral missing-candidate records and are never replaced with invented answers.

盲审包包含调用前选定的 15 个问题 ID 各自全部九次执行。中性代码 `A001` 至 `A135` 替代执行、工作流与重复身份。没有候选的实验失败以中性的缺失候选记录保留，绝不补造答案。

The packet does not contain reference answers, scores, the workflow/repetition mapping, raw provider responses, model configuration, or unselected answers. The generator never reads the held-out reference-answer artifact and never calls a model or paid API.

盲审包不包含参考答案、评分、工作流/重复映射、原始提供商响应、模型配置或未抽中答案。生成器不读取留出参考答案产物，也不调用模型或付费 API。

For every available answer, the human reviewer must split the response into atomic claims, label each claim as `supported`, `unsupported`, or `indeterminate`, verify evidence references, record any safety overreach, and assign frozen failure categories where applicable. A missing candidate is reviewed as an experimental failure; no answer is inferred.

对于每个可用答案，人工审核者必须把回答拆分为原子声明，将每条声明标记为 `supported`、`unsupported` 或 `indeterminate`，核对证据引用，记录任何安全越界，并在适用时分配冻结失败类别。缺失候选按实验失败审核，不推断答案。

The mapping must remain withheld until all 135 entries are complete and saved. Scoring, aggregation, unblinding, post-run audit generation, result upload, and public conclusions remain prohibited during this preparation stage.

在全部 135 项审核完成并保存前，映射必须继续隐藏。本准备阶段仍禁止评分、汇总、揭盲、生成 post-run audit、上传结果或公开结论。
