# Local 3D review / 局部三维审阅

Version 1.0.0 adds a local visual companion to the existing `0.4.0` Change Record contract. It does not add new geometry-diff semantics.

1.0.0 为既有 `0.4.0` 变更记录增加本地视觉辅助，不增加新的几何差分语义。

## Selection and shape / 选择与形状

- One record selects one exact GlobalId. A deleted element uses the previous IFC; other changes use the revised IFC. Multiple records for one GlobalId remain distinct selections.
- Meshes are triangulated from IFC geometry with world coordinates, not reconstructed from bounding boxes. Bounding boxes are only used for neighborhood/camera calculations.
- Up to two unchanged neighbors are chosen within 6 m in the same directly assigned storey. Other changed GlobalIds are excluded from background context.
- Missing or ambiguous identity, geometry or direct storey produces an unavailable state. The deterministic report remains usable.

- 一条记录对应一个精确 GlobalId；删除取旧版，其他变化取新版。同一构件的多条记录仍分别选择。
- 网格由 IFC 原形按世界坐标三角化，不用包围盒代替构件；包围盒仅用于邻域/相机计算。
- 同一直接楼层、6 米邻域内最多选择两个未变化构件；其他变化构件不作为背景。
- 身份、几何或直接楼层缺失、歧义时提示不可用；确定性报告仍可使用。

## Navigation and grid / 导航与网格

Orbit/pan/zoom and focus/fit-context controls are provided. The viewer remains pure black in both application themes. The muted XY grid uses metre-based 1/2/5 spacing, with a major line every five cells and at most 162 line segments. It sits slightly below the displayed bounds and is excluded from element counts, evidence and camera fitting. It is not a real floor, survey datum or building-axis system.

支持旋转/平移/缩放及定位/查看周围。应用深浅主题下三维底色均为纯黑。灰色 XY 参考网格采用米制 1/2/5 间距，每五格主线，最多 162 条线段，位于显示范围下方少许；不计入构件数、证据或相机范围。它不是实际楼板、测量基准或建筑轴网。

## Responsiveness and integrity / 响应与完整性

Geometry conversion runs in a persistent child process. Requests are debounced; stale responses do not replace the latest selection. Source/revised hashes are rechecked even for cache hits. Mesh and viewer caches are bounded; geometry is rendered on demand instead of continuously when idle. The first WebEngine initialization can still briefly pause the UI; no universal frame-rate or latency promise is made.

几何转换由持久后台子进程执行。请求合并处理，过时响应不覆盖最新选择；缓存命中也重新检查新旧文件哈希。网格和查看器缓存有界，静止时不持续重绘。WebEngine 首次初始化仍可能短暂停顿，不承诺通用帧率或延迟指标。

The viewer uses an off-the-record browser profile and session-token loopback URLs, allows only selected local resources, blocks external requests/navigation, and cleans up its worker and temporary session on normal close. A crash may leave temporary local files for later manual cleanup. Exported HTML does not contain this interactive scene.

查看器使用无持久记录的浏览器配置与会话令牌回环 URL，仅允许指定本地资源，阻止外部请求/导航；正常关闭清理子进程和临时会话。崩溃可能残留临时本地文件，需后续手动清理。导出 HTML 不包含此交互场景。
