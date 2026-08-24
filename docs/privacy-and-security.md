# Privacy and security boundary / 隐私与安全边界

This page describes the v0.9.0 privacy boundary while retaining the historical preview design principles. It is a design and verification record, not a security certification.

本文说明 v0.9.0 的隐私边界，并延续早期预览版的设计原则；它是设计与验证记录，不代表安全认证。

## Data flow

| Action / 操作 | Leaves the computer? / 是否离开本机 | Stored automatically? / 是否自动保存 |
|---|---|---|
| Select or drop IFC / 选择或拖入 IFC | No / 否 | Original IFC is not copied / 不复制原始 IFC |
| Deterministic inspect and diff / 确定性检查与差分 | No / 否 | Working JSON/HTML under Windows LocalAppData / 工作 JSON/HTML 保存到 Windows LocalAppData |
| Export JSON or HTML / 导出 JSON 或 HTML | No automatic upload / 不自动上传 | Written only to the user-selected path / 仅写入用户选择的位置 |
| AI disabled / AI 关闭 | No provider request / 不请求服务商 | No API Key required / 不需要 API Key |
| AI provider enabled / AI 服务商开启 | Yes, one HTTPS request to the selected provider / 是，向所选服务商发出一次 HTTPS 请求 | API Key remains in process memory only / API Key 仅保存在进程内存 |

The program does not read `.env.local`, browser credentials, GitHub credentials, or unrelated files. It does not upload IFC files. It does not provide telemetry or automatic update traffic.

程序不读取 `.env.local`、浏览器凭据、GitHub 凭据或无关文件；不上传 IFC 文件；没有遥测或自动更新网络请求。

## Optional AI disclosure

AI is off by default. When explicitly enabled, the request omits absolute paths and source/revised file names, caps input at 200 normalized changes, and uses an absolute HTTPS endpoint without embedded credentials, query strings, or fragments. Normalized records can still contain project-derived data such as element names, storey names, GlobalIds, tags, property names, old/new values, evidence selectors, and—for supported translations—project-world origins and displacement vectors. Use AI only when the project permits those fields to be processed by the selected provider.

AI 默认关闭。用户明确开启后，请求会移除绝对路径和新旧文件名，最多发送 200 条规范化变更，并要求不含嵌入凭据、查询串或片段的绝对 HTTPS 端点。但规范化记录仍可能包含构件名称、楼层名称、GlobalId、Tag、属性名、新旧值、证据位置，以及受支持平移的项目世界坐标原点和位移向量等项目派生数据；只有项目允许这些字段由服务商处理时才开启 AI。

The provider response is capped at 2 MiB, parsed as JSON, checked for the expected explanation shape, and HTML-escaped before report rendering. AI failure is non-blocking: the local deterministic report remains available and the desktop shows a warning.

服务商响应限制为 2 MiB，必须解析为 JSON 并符合预期解释结构；进入 HTML 前会转义。AI 失败不会阻断本地确定性报告，桌面端会显示警告。

## Error and integrity behavior

- Unsupported schema, size, element count, invalid/duplicate GlobalIds, unstable files, unrelated model pairs, and detector failures stop analysis and show an error dialog.
- The old and revised slots cannot use the same file in the desktop workflow.
- Non-`IfcElement` changes, unsupported detector flags, incomplete property value pairs, and non-JSON property values are preserved as unsupported evidence instead of being invented as supported changes.
- Change summaries, unique IDs, path omission, and type-specific value semantics are validated before an artifact is accepted.
- JSON output uses same-directory temporary files and atomic replacement. A unique per-run directory avoids overwriting previous reports.
- Export and report-folder failures show user-visible dialogs. An unexpected Qt/Python exception is routed to a generic desktop error dialog rather than disappearing in a windowed process.

## User responsibilities

- Keep AI off for confidential work unless external processing is authorized.
- Review JSON/HTML before sharing; reports contain hashes and project-derived change evidence, including geometry coordinates when present.
- Never paste API Keys into issues, screenshots, reports, or chat messages.
- Do not upload confidential IFC files to public GitHub issues. Share a minimal synthetic reproducer or private description instead.
- Verify the Release SHA-256. The Windows build is not code-signed, so an unknown-publisher warning is expected.

Security reports should follow [`SECURITY.md`](../SECURITY.md).
