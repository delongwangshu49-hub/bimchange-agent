# Product roadmap / 产品路线图

The roadmap is evidence-driven and intentionally leaves room for adjustment. It describes direction and decision gates, not promised version numbers or dates.

路线图以证据为准，并为后续调整保留空间。它描述方向与决策闸门，不承诺固定版本号或日期。

## Current position / 当前定位

The research release is complete and reproducible. The v0.8.0-rc.1 Windows candidate extends the bounded end-user workflow with one research-gated geometry semantic: verified placement-only translation. Additions, deletions, property-value modifications, desktop review, export, and the optional AI explanation boundary remain in place.

研究发布闭环已经完整可复现。v0.8.0-rc.1 Windows 候选在既有有界用户路径上加入一种经过研究闸门验证的几何语义：经验证的纯放置平移。新增、删除、属性值修改、桌面审阅、导出与可选 AI 解读边界继续保留。

The support claim remains deliberately narrow. One authorized local IFC4 acceptance pair exercised all four supported categories in the desktop workflow, but the private files and outputs remain outside the repository. This is not a broad compatibility study or a promise of arbitrary IFC support.

支持声明仍保持主动收窄。一组获得授权的本地 IFC4 验收对已在桌面流程中覆盖四类受支持变化，但私有文件与输出不进入仓库。这不是大规模兼容性研究，也不构成对任意 IFC 支持的承诺。

## Product direction / 产品主线

1. **Trustworthy bounded core** — preserve the deterministic Change Record as the source of fact; fix only clear, reproducible failures and make boundaries and recovery messages understandable.
2. **Polished review experience** — improve the path from file selection to report, including hierarchy, loading and failure states, change summaries, filtering, export, onboarding, and feedback. Visual work is a product-quality goal, not decoration.
3. **Provider-ready AI layer** — maintain a common provider interface and user-selected settings. DeepSeek, OpenAI, Anthropic, and Google Gemini are selectable after provider-specific request formats, privacy disclosure, offline request/error fixtures, and a deliberate enablement decision. These checks are offline adapter conformance, not evidence of a paid live call. IFC files, local paths, and API keys must remain outside the transmitted report payload and persisted artifacts.
4. **Research-backed evolution** — use small, auditable studies to guide capability choices rather than adding features because they appear impressive.

The agreed audience, visual language, information architecture, settings boundary, and first UI acceptance slice are recorded in [product experience design](product-experience-design.md).

The per-user Windows installer workflow and its verification boundary are recorded in [Windows installer development](windows-installer.md). v0.5.0 was the first release to use this path; v0.8.0-rc.1 continues it as a prerelease candidate.

已达成一致的目标用户、视觉语言、信息架构、设置边界和首个 UI 验收切片记录在[产品体验设计](product-experience-design.md)中。

当前用户 Windows 安装流程及其验证边界记录在 [Windows 安装包开发](windows-installer.md)中；v0.5.0 首次采用该路径，v0.8.0-rc.1 以预发布候选形式延续该路径。

## Research directions / 研究方向

The initial directions are intentionally connected to product decisions:

- **Evidence traceability:** how a normalized change links back to deterministic detector evidence and an operator’s review action.
- **AI explanation reliability:** whether an optional explanation stays faithful to supplied Change Records, avoids invented facts, and communicates uncertainty.
- **Review efficiency:** whether report structure, filtering, and spatial context reduce the time needed to locate and understand a change.

这些方向分别对应：规范化变更如何回链到确定性证据与人工审阅动作；可选 AI 解读是否忠实于已提供 Change Records、避免杜撰并表达不确定性；报告结构、筛选和空间上下文是否能减少定位与理解变更的时间。详见 [research directions](research-directions.md)。

## Spatial change context / 变化位置的空间化呈现

Three-dimensional work is feasible but is a secondary exploration, not the next required product gate. Its target is not a full-building BIM viewer. The useful first outcome is a local, bounded visual context:

- render changed elements plus a small spatial neighbourhood or their containing level/space;
- use distinct colours for added, deleted, and property-modified records;
- let a report row identify the matching `GlobalId` in the local scene;
- show old or new local context as appropriate, before considering overlays or geometry-level visual diffs.

三维工作可行，但属于穿插副线，而不是下一道必经产品闸门。目标不是完整建筑 BIM 浏览器，而是本地、收敛的变化位置上下文：呈现变化构件及少量邻域或所在楼层/空间；以不同颜色区分新增、删除和属性修改；让报告行定位相同 `GlobalId`；先分别显示旧/新局部，再考虑叠模或几何级可视化差分。

The preferred technical route remains one local, offline viewer reused from a small conversion proof into the desktop application. It should start only when it does not displace the review-experience work, and it must retain the existing privacy, packaging, licence, and performance checks. See [3D preview options](three-dimensional-preview-options.md).

首选技术路线仍是一套完全离线的本地查看器：先完成小型转换验证，再复用到桌面程序。它只能在不挤占审阅体验主线的前提下推进，并必须继承隐私、打包、许可证和性能检查。详见[三维预览选项](three-dimensional-preview-options.md)。

## Decision gates / 决策闸门

- A provider becomes selectable only after its data boundary, failure behaviour, and offline adapter tests are explicit.
- A visual redesign proceeds after its user flow and acceptance examples are agreed, not merely from a colour/style preference.
- Spatial viewing progresses only after a report-row-to-`GlobalId` link is credible on bounded data and its benefit to review is demonstrable.
- Broader IFC schemas, Revit integration, automatic updating, and full-model viewing remain demand-led future options.

- 服务商只有在数据边界、失败行为和离线适配测试明确后才可被正式选择。
- 视觉重构应在用户流程和验收示例达成共识后推进，而不只是由配色或风格偏好决定。
- 空间化呈现只有在收敛数据上可可信地完成“报告行到 `GlobalId`”映射，并能证明提升审阅时才继续。
- 更广 IFC Schema、Revit 集成、自动更新和全模型查看仍是由需求驱动的后续选项。
