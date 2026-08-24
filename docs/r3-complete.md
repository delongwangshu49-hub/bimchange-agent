# Complete R3 stable boundary / 完整 R3 稳定边界

> Status: frozen `0.4.0` artifact contract for the `v0.9.0` stable release.
>
> 状态：已冻结为 `v0.9.0` 稳定版的 `0.4.0` 产物契约。

## Supported controlled semantics / 受控支持语义

- Existing addition, deletion, property-value modification, and placement-only translation semantics remain available.
  既有新增、删除、属性值修改和纯放置平移继续可用。
- `extrusion_dimension_change` accepts exactly one Body `IfcExtrudedAreaSolid` with one `IfcRectangleProfileDef`. `profile_x_m`, `profile_y_m`, and `extrusion_depth_m` are reconstructed independently and normalized to metres. Identity, placement, rotation, profile kind and positions, extrusion direction, openings, and projections must remain unchanged.
  `extrusion_dimension_change` 只接受一个 Body `IfcExtrudedAreaSolid` 与一个 `IfcRectangleProfileDef`；分别重建 `profile_x_m`、`profile_y_m`、`extrusion_depth_m` 并统一为米。身份、放置、旋转、轮廓种类与位置、拉伸方向、洞口和投影必须不变。
- `tessellated_vertex_geometry_change` accepts one Body `IfcTriangulatedFaceSet` when placement, identity, topology, openings, and projections remain unchanged. Topology changes remain unsupported.
  `tessellated_vertex_geometry_change` 只接受一个 Body `IfcTriangulatedFaceSet`，且放置、身份、拓扑、洞口和投影不变。拓扑变化仍不支持。
- `relationship_modified` covers direct storey/space containment, aggregation/decomposition, type assignment, and direct material association, with old and new references.
  `relationship_modified` 覆盖直接楼层/空间包含、聚合/分解、类型关系和直接材料关联，并显示旧关系和新关系。

## Detector decision / 检测器决策

Direct comparison of the declared IFC entity chain is the primary deterministic detector for extrusion dimensions and relationships. The tessellated subtype requires both an IfcDiff `geometry_changed` flag and independent direct reconstruction. IfcDiff 0.8.5 raw output is retained as supplemental evidence for the other R3 subtypes. Controlled audit found that an XDim-only symmetric profile change can produce no geometry flag; relationship comparison can emit unrelated flags or miss aggregate/type flags; and 0.8.5 has no material mode.

对于拉伸尺寸和关系变化，直接比较声明范围内的 IFC 实体链是主要确定性检测器；网格子类型则同时要求 IfcDiff `geometry_changed` 标志和独立直接重建。对其余 R3 子类型，IfcDiff 0.8.5 原始输出仅作为补充证据保留。受控审计发现：仅修改 XDim 的对称轮廓可能没有 geometry flag；关系比较可能产生无关标志或漏掉 aggregate/type 标志；0.8.5 也没有材料模式。

## Gate result / 闸门结果

- 10 controlled supported cases; two clean runs with identical normalized semantics;
- unique reconstruction resolution `100%`;
- fixed tamper matrix `16/16` rejected, false acceptance `0`;
- privacy violations `0`; model/API calls `0`;
- 46 product/desktop/reporting tests and 9 complete-R3 research tests passed locally before the stable-version freeze; the release gate reruns these suites.

- 10 个受控支持 case；两次干净运行的规范化语义一致；
- 唯一重建解析率 `100%`；
- 固定篡改矩阵 `16/16` 拒绝，错误接受 `0`；
- 隐私违规 `0`，模型/API 调用 `0`；
- 稳定版本冻结前，本地通过 46 项产品/桌面/报告测试和 9 项完整 R3 研究测试；发布闸门会重新运行这些套件。

These results do not establish arbitrary IFC, arbitrary extrusion/profile combinations, tessellated topology changes, nested material usage, exporter independence, or professional engineering validity.

上述结果不证明任意 IFC、任意拉伸/轮廓组合、网格拓扑变化、嵌套材料用法、跨导出器独立性或专业工程正确性。
