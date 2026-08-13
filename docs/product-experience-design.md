# Product experience design / 产品体验设计

This document defines the desktop experience direction without assigning a release number or date.

本文定义桌面产品体验方向，不预先指定版本号或发布日期。

## Audience and outcome / 用户与目标

The primary audience is practising BIM professionals reviewing bounded IFC revisions. A user should be able to select two IFC versions, understand analysis progress, review supported changes, inspect evidence, and export a report without learning the underlying implementation.

主要用户是审阅明确边界内 IFC 版本的实际 BIM 工程人员。用户无需理解底层实现，即可完成选择两个 IFC 版本、理解分析进度、审阅受支持变更、查看证据并导出报告。

## Visual direction / 视觉方向

- Swiss International Style: grid-led hierarchy, clear typography, restrained controls, and generous working space.
  瑞士国际主义风格：以网格、字体层级、克制控件和清晰工作空间为主。
- Earth-toned light and dark themes with neutral surfaces and semantic change accents.
  提供大地色系浅色与深色主题，以中性表面和具有语义的变更色为主。
- Product state and evidence are visually stronger than decoration.
  产品状态和证据信息的视觉优先级高于装饰。

## Information architecture / 信息架构

1. **Select files** — previous and revised IFC drop zones, bounded-support notice, privacy note, and one primary action.
   **选择文件**——旧版与新版 IFC 拖拽区、支持边界、隐私提示和唯一主操作。
2. **Analyse changes** — persistent progress state while inputs and settings are locked.
   **分析变更**——分析期间持续显示进度，并锁定输入与设置。
3. **Review report** — summary metrics, search and filters, change table, selected-record evidence, optional AI explanation, and export actions.
   **审阅报告**——摘要指标、搜索筛选、变更表、选中记录证据、可选 AI 解读和导出操作。

## Settings boundary / 设置边界

Appearance, language, and AI provider configuration live in one settings center. The main window exposes only an AI explanation switch. Theme and language preferences may be persisted locally; API keys remain in memory for the current session and are never persisted.

外观、语言和 AI 服务商配置集中在统一设置中心。主界面只保留 AI 解读开关。主题与语言偏好可在本地持久化；API Key 只保存在当前运行内存中，绝不持久化。

## AI provider boundary / AI 服务商边界

The settings center exposes four explicit adapters: DeepSeek Chat Completions, OpenAI Responses, Anthropic Messages, and Google Gemini Generate Content. Each adapter has a provider-specific request shape and response parser behind one application-level factory. Selection never implies silent fallback to another provider.

设置中心提供四个明确适配器：DeepSeek Chat Completions、OpenAI Responses、Anthropic Messages 与 Google Gemini Generate Content。每个服务商都通过统一应用工厂使用独立的请求结构和响应解析器；选择某服务商后绝不静默回退到其他服务商。

Before an adapter is selectable, synthetic offline tests must cover its endpoint, authentication-header placement, structured-output request, response parsing, bounded payload, generic failure behaviour, and removal of local file names and paths. These tests establish adapter conformance only; they do not claim that a paid live request has been exercised. Live calls always require an explicit user action and a session-only key.

适配器只有在合成离线测试覆盖端点、认证请求头、结构化输出请求、响应解析、载荷上限、通用失败行为以及本地文件名/路径裁剪后才可选择。这类测试只证明适配器协议符合性，不代表已执行付费在线调用。在线调用始终需要用户明确操作和仅限本次运行的 Key。

## First vertical-slice acceptance / 首个纵向切片验收

- Runtime switching between Simplified Chinese and English.
  运行时切换简体中文和英文。
- System, light, and dark appearance choices.
  支持跟随系统、浅色和深色主题。
- Main-window AI switch synchronized with the unified settings center.
  主界面 AI 开关与统一设置中心保持同步。
- Search plus change-type, entity-type, and storey filters.
  支持搜索及按变化类型、实体类型、楼层筛选。
- A selected change exposes its values and evidence selector without changing the frozen Change Record contract.
  选中变更可查看前后值与证据选择器，不修改冻结的 Change Record 契约。
- Offline UI tests use synthetic Change Records and make no IFC or model API calls.
  离线 UI 测试只使用合成 Change Records，不读取 IFC，也不调用模型 API。

## Interaction refinement / 交互优化

- AI enablement uses an accessible animated switch with explicit `local only` and `bounded records sent` states. The thumb moves horizontally over 180 ms; AI remains off by default.
- Provider failures retain the deterministic report and are classified into configuration, authentication, endpoint/model, rate/quota, provider availability, network, timeout, invalid JSON, and response-shape categories without exposing keys or response bodies.
- Change tables scroll per pixel and update in batches. Splitters use deferred (non-opaque) resize to avoid repeatedly repainting the full table while the user drags a divider.
- Report splitters enforce usable minimum and maximum pane sizes throughout dragging; neither the table nor evidence pane can be collapsed beyond the review boundary.
- Combo-box arrows are supplied explicitly for light and dark themes, and the default 1120×720 window keeps the primary workflow compact without compromising the minimum 920×640 layout.
- At narrower widths, the evidence pane moves below the table so the five primary fields keep the full content width. Elided cells expose their complete value through a tooltip and the evidence pane.
- Corners follow a restrained Windows-like radius. The dark theme is graphite and neutral gray rather than yellow-brown, with muted terracotta reserved for active state and focus.

- AI 启用采用具备无障碍名称的动画开关，明确区分“仅本地”和“发送受限记录”；滑块在 180ms 内横向移动，默认仍为关闭。
- 服务商失败不会影响确定性报告，并区分设置、认证、端点/模型、限流/额度、服务不可用、网络、超时、无效 JSON 与响应结构；不显示 Key 或服务商响应正文。
- 变更表使用逐像素滚动和批量刷新；分隔条采用延迟调整，拖拽时不持续重绘整张表格。
- 报告分隔条在拖拽过程中持续限制可用的最小与最大面板尺寸，表格和证据面板都不会被压缩到审阅边界之外。
- 下拉箭头在深浅色主题中均使用显式资源；默认 1120×720 窗口在不破坏 920×640 最小布局的前提下保持紧凑。
- 窄窗口下证据面板移到表格下方，使五个主要字段获得完整横向宽度；被截断的单元格可通过 Tooltip 和证据面板查看完整值。
- 圆角采用克制的 Windows 风格；深色主题改为石墨与中性灰，仅用低饱和陶土色表达激活与焦点状态。

## Brand assets / 品牌资产

The app icon depicts two BIM revisions, a highlighted changed zone, and a traceable evidence marker. The same source is supplied as a transparent PNG for the application/taskbar and as a multi-resolution ICO embedded in the Windows executable and installer. A square product-cover PNG is retained for future release artwork.

应用图标以两个 BIM 版本、高亮变化区域和可追溯证据标记构成。透明 PNG 用于应用与任务栏，多尺寸 ICO 嵌入 Windows EXE 和安装器；同时保留方形产品封面 PNG，供后续 Release 视觉使用。
