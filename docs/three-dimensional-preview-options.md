# Three-dimensional preview options / 三维预览后续路线

Three-dimensional IFC viewing is feasible, but it is not a small decoration on the current report page. It adds geometry conversion, GPU rendering, camera controls, object picking, GUID-to-mesh mapping, visual diff rules, large-model memory management, and a second packaging/licensing surface.

IFC 三维查看可行，但它不是在报告页上增加一个小组件那么简单。它会同时引入几何转换、GPU 渲染、相机控制、构件拾取、GUID 与网格映射、变更着色规则、大模型内存管理，以及新的打包和许可证边界。

## Route assessment

| Route | First useful result | Product difficulty | Main trade-off |
|---|---:|---:|---|
| Native PySide6/OpenGL with IfcOpenShell tessellation | 2–4 focused weeks | High | Maximum control, but camera, picking, materials and performance are all our responsibility |
| Embedded web viewer with IFC converted to GLB/XKT | 1–3 focused weeks | Medium–high | Faster viewer UX, but adds Qt WebEngine/JavaScript assets and licensing review |
| Open generated GLB in an external viewer | 3–7 focused days | Medium | Lowest implementation cost, but the experience leaves BIMChange-Agent and GUID interaction is weaker |

These are planning ranges, not commitments. Actual effort depends on exporter compatibility, desired visual-diff precision, and whether the viewer must support selecting a report row and highlighting the same IFC element.

## Lowest-cost integrated strategy

The best cost/integration balance is not to choose permanently between an external page and an embedded viewer. Build one **offline local Three.js viewer** and reuse it in two steps:

1. Generate a GUID-preserving GLB and open the local viewer HTML externally for a 2–3 day conversion/rendering proof.
2. After the same viewer passes load-time and memory checks, embed it in the existing PySide6 application with `QWebEngineView` and a local-only `QWebChannel` bridge.

This approach keeps the user experience integrated in the target product while avoiding two separate rendering implementations. It does add PySide6 Addons/Qt WebEngine to the package and therefore requires a new size, license and SmartScreen audit. Bundle Three.js and all viewer assets locally; do not use a CDN or hosted viewer.

最具性价比且保持一体化的策略，不是永久在“外部网页”和“内嵌查看器”之间二选一，而是开发一套**完全离线的本地 Three.js 查看器**并分两步复用：先用保留 GUID 的 GLB 加本地 HTML，在 2–3 天内验证转换和渲染；通过加载时间与内存检查后，再用 `QWebEngineView` 和仅本地通信的 `QWebChannel` 嵌入现有 PySide6 软件。这样最终体验仍是一体化软件，同时避免维护两套渲染实现。代价是加入 PySide6 Addons/Qt WebEngine 后必须重新审计包体、许可证和 SmartScreen；Three.js 与全部资源必须本地打包，不使用 CDN 或在线查看器。

## Recommended later slice

When the desktop MVP is stable, start with a bounded proof:

1. Convert one accepted IFC4 file to GLB using IfcOpenShell geometry serialisation or a pinned IfcConvert executable.
2. Preserve element GUIDs in the serialised output.
3. Display one model at a time with orbit, pan, zoom, fit-to-view and reset; set explicit conversion/load-time and memory budgets.
4. Embed the same local viewer in the report page.
5. Add report-row-to-GUID highlighting through a narrow bridge only after basic rendering is reliable.
6. Add old/new switching, then colour-coded changes; overlay and geometry-level diff come last.

IfcOpenShell documents both a multicore geometry iterator and GLB/glTF serialisation with optional element GUIDs: <https://docs.ifcopenshell.org/ifcopenshell-python/geometry_processing.html>.

## Recommendation

Do not place 3D preview in Preview 1. Keep the report artifact and GUI model keyed by `GlobalId`, which preserves a clean future integration point without making the current package depend on a rendering engine. Begin the conversion/viewer spike after the Aug 18 budget checkpoint; a credible integrated proof is roughly 5–8 focused development days, while a hardened old/new highlighting experience remains a 2–3 week slice. These are planning ranges, not commitments.
