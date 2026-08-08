# Gate 4 Deterministic Held-Out IFC Fixture

# Gate 4 确定性留出 IFC 样例

## Outcome / 结果

The first independent Gate 4 IFC fixture is implemented offline as dataset `gate4-controlled-heldout-v0.1.0`. It contains separate IFC4 source and revised models, an authoritative operation ledger, Schema `0.1.0` Change Records, and retained IfcDiff 0.8.5 evidence. No model-provider call is part of this step.

首个独立 Gate 4 IFC 样例已作为数据集 `gate4-controlled-heldout-v0.1.0` 离线实现。产物包括独立的 IFC4 源模型与修订模型、权威操作账本、符合 Schema `0.1.0` 的 Change Record，以及保留的 IfcDiff 0.8.5 证据。本步骤不包含任何模型提供商调用。

The source and revised models each contain 48 elements across `IfcBeam`, `IfcColumn`, `IfcWall`, and `IfcSlab`. Exactly 40 source elements remain unchanged. Every element is directly contained by one of three explicit storeys: `Ground Floor`, `Level 01`, or `Roof`.

源模型与修订模型各包含 48 个构件，覆盖 `IfcBeam`、`IfcColumn`、`IfcWall` 与 `IfcSlab`；其中恰好 40 个源模型构件保持不变。每个构件均通过明确关系直接归属于 `Ground Floor`、`Level 01` 或 `Roof` 三个楼层之一。

## Controlled changes / 受控变更

The frozen 12-cell matrix is implemented exactly: four additions, four deletions, and four property modifications; each storey contains four changes. Each of the four entity types appears once on every storey and therefore has three changes in total.

冻结的 12 格矩阵已被完整实现：新增、删除与属性修改各 4 条，每个楼层各 4 条。四种构件类型均在三个楼层各出现一次，因此每种构件类型合计 3 条变更。

The frozen design prose also says “four per entity type.” That phrase is arithmetically incompatible with both the exact 12-change requirement and the frozen 4-by-3 matrix because it would require 16 changes. The implementation treats the explicit matrix and exact total as authoritative. The frozen design file is not edited, and this interpretation is recorded before question generation or any model call.

冻结设计正文另有“每种构件类型 4 条”的表述，但它与“恰好 12 条”及已冻结的 4×3 矩阵在算术上不相容，因为该表述会要求 16 条变更。本实现以明确矩阵和总数要求为权威；冻结设计文件保持不变，并在生成问题或发起任何模型调用前记录此解释。

| Entity type | Ground Floor | Level 01 | Roof |
|---|---|---|---|
| `IfcBeam` | added | deleted | `LoadBearing`: false → true |
| `IfcColumn` | `IsExternal`: true → false | added | deleted |
| `IfcWall` | deleted | `FireRating`: `"60"` → `"90"` | added |
| `IfcSlab` | added | deleted | `LoadBearing`: false → true |

上表同时给出四种构件在三个楼层中的完整变更分布；属性修改沿用冻结规格中的字段与旧值/新值。

## Determinism and independent checks / 确定性与独立校验

All IFC roots use UUIDv5-derived fixed GlobalIds. IFC headers, names, tags, property values, spatial relationships, owner-history timestamps when present, and IFC SET ordering are normalized. Two clean generations reproduce byte-identical source IFC, revised IFC, operation ledger, and Change Record files.

所有 IFC 根实体均使用由 UUIDv5 确定性派生的固定 GlobalId。IFC 头信息、名称、Tag、属性值、空间关系、存在时的 OwnerHistory 时间戳与 IFC SET 顺序均已规范化。两次干净生成可逐字节复现源 IFC、修订 IFC、操作账本与 Change Record 文件。

The verifier independently checks the frozen matrix, Schema validity, hashes, IFC4 schema, spatial hierarchy, GlobalId uniqueness, neutral names and tags, model-side presence, property values, unchanged-element equality, and retained IfcDiff output. IfcDiff reports exactly 4 added, 4 deleted, and 4 property-modified GUIDs with no extra change.

验证器独立检查冻结矩阵、Schema 合规性、哈希、IFC4 Schema、空间层级、GlobalId 唯一性、中性名称与 Tag、实体所在版本、属性值、不变构件一致性及保留的 IfcDiff 输出。IfcDiff 恰好报告 4 个新增、4 个删除与 4 个属性修改 GUID，没有额外变更。

Negative tests confirm that an extra IfcDiff GUID and an answer-bearing element name are rejected.

负例测试确认：额外的 IfcDiff GUID 与带答案提示的构件名称都会被拒绝。

## Reproduce / 复现

Run the foundation guard first, then the complete offline fixture pipeline:

先运行 foundation guard，再执行完整的离线样例流程：

```powershell
.\.venv\Scripts\python.exe scripts\verify_gate4_foundation.py
.\.venv\Scripts\python.exe scripts\run_gate4_fixture.py
.\.venv\Scripts\python.exe scripts\test_gate4_fixture.py
```

The retained IFC hashes are:

保留 IFC 的哈希如下：

- Source SHA-256: `71cf3353c6f2fd8f3182dbb2e38136dfa6f28f383e74cee629d235b2fb61ddb6`
  源模型 SHA-256 如上。
- Revised SHA-256: `a4c391bb86802089f8851d04c773580583b90bdb81578efad2425c6da6542d9e`
  修订模型 SHA-256 如上。

## License and scope / 许可与范围

The generated dataset artifacts are released under Creative Commons Attribution 4.0 International (CC BY 4.0), attributed to “BIMChange-Agent Gate 4 Held-Out Dataset.” Generator and verifier code remain under the repository MIT license.

生成的数据集产物采用 Creative Commons Attribution 4.0 International（CC BY 4.0）许可，署名为“BIMChange-Agent Gate 4 Held-Out Dataset”；生成器与验证器代码继续采用仓库的 MIT 许可。

All changes are synthetic test fixtures. They are not engineering, constructability, compliance, coordination-priority, or safety recommendations. Geometry and relationship changes remain outside this scored fixture.

所有变更均为合成测试样例，不构成工程、可施工性、合规、协调优先级或安全建议；几何与关系变更仍不属于本轮计分样例。
