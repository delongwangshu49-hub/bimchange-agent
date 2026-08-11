# Product roadmap / 产品路线图

The roadmap is evidence-driven. Dates are planning ranges, not promises. A phase advances only when its acceptance checks pass.

路线图以证据为准；日期是规划范围，不是承诺。只有验收点通过后才进入下一阶段。

## Current position — 2026-08-11

The research-release loop is complete and reproducible. v0.2.0 Preview 1 adds the first end-user-shaped Windows vertical slice: bounded IFC4 input, deterministic diff, normalized records, desktop report, export, optional DeepSeek, and portable packaging.

科研发布闭环已经完整可复现；v0.2.0 Preview 1 首次形成面向普通用户形态的 Windows 纵向切片：受限 IFC4 输入、确定性差分、规范化记录、桌面报告、导出、可选 DeepSeek 与便携打包。

## Near-term milestones

| Window | Focus | Acceptance point |
|---|---|---|
| Aug 11–12 | Publish Preview 1 checkpoint | Public source, pre-release ZIP/checksum, tutorial, privacy and license notices verified |
| Aug 12–14 | Real/representative IFC4 feedback | At least one authorized small fixture; failures classified without expanding the support claim |
| Aug 15–17 | Critical hardening only | Regression suite, error wording, packaging fixes; Preview 2 only if a material defect is found |
| Aug 18 onward | Resume broader development after expected quota/credit refresh | Reconfirm available budget, then start the bounded 3D conversion/viewer spike |

The account UI's remaining 40% is a relative indicator and is not a precise token or task count. Until Aug 18, reserve capacity for high-value compatibility failures and release corrections; defer broad visual redesign, multi-provider work, Revit, and full 3D implementation.

界面显示的剩余 40% 是相对指标，不能精确换算 token 或任务数。8 月 18 日前应把额度留给真实兼容故障和发布修复，暂缓大规模视觉重构、多服务商、Revit 与完整三维实现。

## Macro phases

1. **Preview stabilization** — real IFC fixtures, explicit exporter matrix, failure taxonomy, performance measurement, cancellation and recovery.
2. **Trustworthy distribution** — repeatable CI build, code signing, malware/SmartScreen checks, SBOM/license automation, release-channel metadata.
3. **Integrated review experience** — cost-controlled 3D, report-row highlighting, saved review packages, clearer unsupported-change presentation.
4. **Selective ecosystem expansion** — additional AI providers, broader schema/exporter support, update checks, Revit integration, only where evidence justifies cost.

## 3D strategy

Use one offline Three.js viewer codebase twice: first as a local HTML proof over GUID-preserving GLB, then embed that exact viewer in Qt WebEngine. This avoids paying for a throwaway external prototype and avoids building a native OpenGL viewer from scratch. Start with one model, orbit/pan/zoom/reset, and load-time/memory budgets; add row-to-GlobalId highlighting next; overlay and geometry-level visual diff last.

三维采用“一套本地 Three.js 查看器，两阶段复用”：先以保留 GUID 的 GLB 加本地 HTML 验证，再把同一查看器嵌入 Qt WebEngine。这样既避免外部原型被推翻，也避免从零开发原生 OpenGL。先做单模型与基础相机操作、加载/内存预算，再做报告行到 GlobalId 高亮，最后才做叠模和几何级可视化差分。
