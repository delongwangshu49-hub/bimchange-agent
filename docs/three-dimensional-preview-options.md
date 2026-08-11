# Spatial change context / 变化位置的空间化呈现

## Purpose / 目标

The later visual feature is not a commitment to build a complete BIM viewer. Its purpose is to make an already-detected Change Record easier to locate and understand: **where did the change occur, and what is immediately around it?**

后续视觉功能不承诺建设完整 BIM 浏览器。它的目标是让已经检测到的 Change Record 更容易被定位和理解：**变化发生在哪里，周围是什么？**

## Bounded first outcome / 收敛的首个结果

- Render only changed elements and a small neighbourhood, their containing storey, or their containing space.
- Colour added, deleted, and property-modified records differently; never use colour as the only source of meaning.
- Select a report row to identify the corresponding `GlobalId` in the local scene.
- Show old context for a deletion and new context for an addition/property change when appropriate.
- Keep Change Records and deterministic detector evidence authoritative; the scene is an explanation surface.

- 只渲染变化构件及小范围邻域、所在楼层或空间。
- 用不同颜色区分新增、删除和属性修改；颜色不能成为唯一信息来源。
- 点击报告行后，在本地场景中识别相同 `GlobalId`。
- 对删除适时显示旧版上下文；对新增/属性修改适时显示新版上下文。
- Change Records 与确定性检测证据仍是事实源；场景只是解释界面。

## Feasibility and route / 可行性与路线

This is technically feasible because the product already keeps report records keyed by `GlobalId`. It still requires IFC geometry conversion, GUID-to-mesh mapping, local rendering, camera controls, performance limits, and new packaging/licence checks; it should therefore remain a secondary exploration until the review experience is solid.

该方向技术上可行，因为产品已用 `GlobalId` 关联报告记录。但它仍需要 IFC 几何转换、GUID 到网格的映射、本地渲染、相机控制、性能限制和新的打包/许可证检查；因此在审阅体验主线稳定前，应保持为穿插探索。

The cost-conscious route is one offline local viewer, first proven with a small GUID-preserving IFC-to-GLB conversion, then embedded into the desktop application only if the same code demonstrates value. Bundle all assets locally; do not send models to a hosted viewer or use a CDN.

兼顾成本与一体化的路线是一套离线本地查看器：先用保留 GUID 的小型 IFC→GLB 转换验证，再只有在同一代码证明价值时嵌入桌面程序。所有资源本地打包；不把模型发送到托管查看器，也不使用 CDN。

## Deferred work / 后置工作

Full-model navigation, old/new overlays, geometry-level visual diffs, rich picking tools, and a native OpenGL implementation are explicitly deferred. They should follow measurable review benefit, not precede it.

全模型漫游、旧新叠模、几何级可视化差分、复杂拾取工具和原生 OpenGL 实现均明确后置。它们应由可测的审阅收益驱动，而不是先于收益出现。
