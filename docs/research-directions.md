# Research directions / 科研与能力探索方向

## Why this exists / 文档目的

Research work should strengthen the product's trustworthiness and guide future capability choices. It is not a separate promise of a large evaluation programme.

科研工作应增强产品可信度，并为后续能力选择提供依据；它不是对大规模评测计划的单独承诺。

## Direction 1 — evidence traceability / 证据可追溯性

Study how a normalized Change Record can retain a concise link to deterministic detector evidence, declared input limits, and a reviewer’s verification action. A useful outcome is an auditable path from a report row back to the reason it was produced.

研究规范化 Change Record 如何保留到确定性检测证据、已声明输入边界和审阅者验证动作的简洁回链。目标是让报告行能可审计地回到其产生原因。

## Direction 2 — AI explanation reliability / AI 解读可靠性

Evaluate optional provider explanations against supplied Change Records: factual faithfulness, unsupported additions, missing caveats, and clarity about uncertainty. The deterministic artifact remains the reference; an AI explanation must not create new engineering facts.

针对已提供的 Change Records 评估可选服务商解读：事实忠实度、无依据新增、遗漏限制和不确定性表达。确定性产物始终是参照；AI 解读不得创造新的工程事实。

## Direction 3 — review efficiency / 审阅效率

Compare bounded report presentations such as summary cards, filters, evidence links, and later spatial context. Focus on whether a reviewer can locate, understand, and verify a change with less time or ambiguity, rather than treating visual novelty as the outcome.

比较摘要卡片、筛选、证据链接及后续空间上下文等收敛的报告表达方式。关注审阅者是否能以更少时间或更低歧义定位、理解和验证变化，而不是把视觉新奇性当作结果。

## Working principles / 工作原则

- Use authorised or controlled non-sensitive data only.
- Preserve reproducible prompts, deterministic inputs, measures, and limitations.
- Do not claim general IFC compatibility or professional engineering validation from small samples.
- Promote a research result into a product feature only when its user value and operational cost are both clear.

- 只使用获得授权或受控的非敏感数据。
- 保留可复现的提示词、确定性输入、度量与限制。
- 不从小样本推导通用 IFC 兼容性或专业工程验证结论。
- 只有用户价值和运行成本都明确时，才把研究结果推进为产品功能。

## Current checkpoint — deterministic traceability / 当前检查点：确定性证据追溯

The first isolated traceability slice now binds each supported Change Record to the input content hashes, the complete detector configuration, the raw deterministic result, a structured evidence locator, and an independently reconstructed normalized fact. Its fail-closed verifier covers added, deleted, and property-value-modified records.

首个隔离式证据追溯切片现已把每条受支持 Change Record 绑定到输入内容哈希、完整检测器配置、原始确定性结果、结构化证据位置和独立重建的规范化事实；失败关闭验证覆盖新增、删除和属性值修改三类记录。

On the repository-controlled fixture, and separately on one authorised local IFC4 A/B/C sample set that is not published with the repository, the technical gate reached 100% unique trace resolution, two identical clean rebuilds, complete rejection of the fixed 13-case tamper matrix, zero false acceptance, zero path leakage, and zero model/API calls. The local sample result is a bounded external replication, not evidence of general IFC4 compatibility, professional engineering correctness, or user benefit.

在仓库受控 fixture，以及一组未随仓库公开的本地授权 IFC4 A/B/C 样本上，技术闸门均达到：证据唯一解析率 100%、两次干净重建一致、固定 13 项篡改全部拒绝、误接受 0、路径泄漏 0、模型/API 调用 0。本地样本结果只是有界外部复现，不证明通用 IFC4 兼容性、专业工程正确性或用户收益。

One authorised IFC2X3 file has passed a path-free inventory for readability and complete, unique IfcRoot GlobalIds. Because no controlled same-schema revision pair is registered yet, it is only a schema-boundary observation. It does not change the product's exact IFC4 boundary and does not support an IFC2X3 diff or traceability claim.

一个授权 IFC2X3 文件已通过不记录路径的可读性与 IfcRoot GlobalId 完整唯一性盘点。由于尚未登记同模式受控修订对，它目前只构成模式边界观察，不改变产品的精确 IFC4 边界，也不支持 IFC2X3 差分或追溯已通过的表述。

The prepared single-developer review protocol remains unexecuted. If used later, its results will be reported only as design diagnostics, never as a population user study.

已经准备的单开发者审阅协议仍未执行。若以后执行，其结果只作为设计诊断，不作为群体用户研究。
