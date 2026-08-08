# Gate 4 Held-Out Question and Direct-Input Artifacts

# Gate 4 留出问题与 Direct 输入产物

## Outcome / 结果

The first Gate 4 pre-call content layer is implemented entirely offline for dataset `gate4-controlled-heldout-v0.1.0`. It contains 40 English held-out questions, deterministic reference answers derived by applying each structured selection to the 12 frozen Change Records, and a Direct LLM input containing only separate source and revised IFC inventories. No model-provider call was made.

数据集 `gate4-controlled-heldout-v0.1.0` 的首个 Gate 4 调用前内容层已完全离线实现。产物包括 40 道英文留出问题、通过把每个结构化筛选确定性应用于 12 条冻结 Change Record 得到的参考答案，以及仅包含源 IFC 与修订 IFC 两份独立清单的 Direct LLM 输入。本步骤未发起任何模型提供商调用。

The frozen allocation is exact:

冻结分配完全符合规格：

| Category | Count | Reference status |
|---|---:|---|
| `summary` | 4 | `answered` |
| `fact_lookup` | 6 | `answered` |
| `filtered_lookup` | 14 | `answered` |
| `property_change` | 6 | `answered` |
| `negative_control` | 5 | `not_found` |
| `evidence_boundary` | 5 | `insufficient_evidence` |

| 类别 | 数量 | 参考状态 |
|---|---:|---|
| `summary` | 4 | `answered` |
| `fact_lookup` | 6 | `answered` |
| `filtered_lookup` | 14 | `answered` |
| `property_change` | 6 | `answered` |
| `negative_control` | 5 | `not_found` |
| `evidence_boundary` | 5 | `insufficient_evidence` |

## Deterministic construction / 确定性构建

Question IDs continue from `gate3-q09-...` through `gate3-q48-...` only because the protected evaluation-question Schema fixes that prefix. The artifact still declares `split: held_out` and the Gate 4 dataset ID. Every reference result is selected offline with the frozen conjunction semantics; an answered or evidence-boundary item must select records, while a negative control must select none.

问题 ID 从 `gate3-q09-...` 延续至 `gate3-q48-...`，仅用于兼容受保护的 evaluation-question Schema 固定前缀。产物仍明确声明 `split: held_out` 与 Gate 4 数据集 ID。所有参考结果均按冻结的合取语义离线筛选；已回答题与证据边界题必须选中记录，负控题必须不选中任何记录。

The Direct input independently enumerates 48 source and 48 revised `IfcElement` objects with entity type, GlobalId, neutral Name and Tag, explicit storey, and scalar property-set values. It contains no Change Record, selected result, precomputed difference, reference answer, engineering judgment, or evidence field.

Direct 输入分别独立列出源版本与修订版本各 48 个 `IfcElement`，内容仅包括实体类型、GlobalId、中性 Name 与 Tag、明确楼层及标量属性集值。其中不含 Change Record、筛选结果、预计算差异、参考答案、工程判断或证据字段。

## Independent offline verification / 独立离线验证

Run the guarded generators and verifier with the repository environment:

使用仓库环境运行受守卫保护的生成器与验证器：

```powershell
.\.venv\Scripts\python.exe scripts\generate_gate4_question_artifacts.py
.\.venv\Scripts\python.exe scripts\generate_gate4_direct_input.py
.\.venv\Scripts\python.exe scripts\verify_gate4_question_artifacts.py
.\.venv\Scripts\python.exe scripts\test_gate4_question_artifacts.py
```

The independent verifier confirms all frozen category and status counts, Schema validity, contiguous unique IDs, deterministic selection results, and exact correspondence between the Direct inventories and both IFC files. Each of the 12 Change Records is covered by at least three non-summary questions and at least two summary questions, exceeding the frozen minima of two and one.

独立验证器会核对全部冻结类别与状态数量、Schema 有效性、连续且唯一的 ID、确定性筛选结果，以及 Direct 清单与两个 IFC 文件的精确一致性。12 条 Change Record 中的每一条都至少被三个非摘要问题和两个摘要问题覆盖，超过冻结要求的至少两个与至少一个。

Anti-leakage checks find no normalized exact match with the eight development questions, no development-only GlobalId, no reference-answer string or precomputed change identifier in the Direct input, and no forbidden difference or evidence key. Negative tests reject a duplicate ID, a repeated development question, injected reference text, and an injected change key.

防泄漏检查确认：与八道开发问题不存在规范化逐字匹配，不含开发集专用 GlobalId，Direct 输入中不存在参考答案字符串或预计算变更标识，也不存在被禁止的差异或证据字段。负例测试能够拒绝重复 ID、复用开发问题、注入参考文本与注入变更字段。

Retained SHA-256 values:

保留的 SHA-256：

- Questions: `f53874e9892aeeec43f1fa15b3c79aa9d3a2985cb5d68a7a8807147eea5cbf6b`.
  问题集：`f53874e9892aeeec43f1fa15b3c79aa9d3a2985cb5d68a7a8807147eea5cbf6b`。
- Reference answers: `7a36081063c735e69b7290722f71b24b87546c49c6af32ec4ba60d2a6a8e9a8c`.
  参考答案：`7a36081063c735e69b7290722f71b24b87546c49c6af32ec4ba60d2a6a8e9a8c`。
- Direct input: `7c91ee5d53dbed7777b1f3a17fb1fca4b0e2dce30b6f95ca99903ffd794796dc`.
  Direct 输入：`7c91ee5d53dbed7777b1f3a17fb1fca4b0e2dce30b6f95ca99903ffd794796dc`。

These hashes are retained implementation evidence, not the final pre-call freeze manifest. The run schedule, audit samples, budget amendment record, orchestration wrapper, and complete manifest remain later guarded steps. Model calls remain prohibited until those steps pass review.

这些哈希属于已保留的实现证据，并非最终调用前冻结清单。执行计划、审核样本、预算变更记录、编排外壳与完整清单仍属于后续受守卫步骤；在这些步骤审核通过前，仍禁止发起模型调用。
