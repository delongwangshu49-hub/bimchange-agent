"""Deterministic, self-contained HTML reporting for product artifacts."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .product_core import validate_product_artifact


def _text(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (dict, list, bool, int, float)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _escape(value: Any) -> str:
    return html.escape(_text(value), quote=True)


def _change_rows(artifact: dict[str, Any]) -> str:
    rows: list[str] = []
    for change in artifact["changes"]:
        storey = change["location"]["building_storey"]
        field = change["field"]
        field_text = (
            f"{field['property_set']}.{field['name']}" if field is not None else "—"
        )
        rows.append(
            "<tr>"
            f"<td><span class='badge'>{_escape(change['change_type'])}</span></td>"
            f"<td>{_escape(change['entity_type'])}</td>"
            f"<td><code>{_escape(change['global_id'])}</code></td>"
            f"<td>{_escape(storey['name'] if storey else None)}</td>"
            f"<td>{_escape(field_text)}</td>"
            f"<td>{_escape(change['old_value'])}</td>"
            f"<td>{_escape(change['new_value'])}</td>"
            "</tr>"
        )
    if not rows:
        return "<tr><td colspan='7' class='empty'>没有检测到受支持的变更</td></tr>"
    return "".join(rows)


def _warning_items(artifact: dict[str, Any]) -> str:
    return "".join(f"<li>{_escape(item)}</li>" for item in artifact["warnings"])


def _unsupported_rows(artifact: dict[str, Any]) -> str:
    return "".join(
        "<tr>"
        f"<td><code>{_escape(item['global_id'])}</code></td>"
        f"<td>{_escape(item['reason'])}</td>"
        f"<td><code>{_escape(item['selector'])}</code></td>"
        "</tr>"
        for item in artifact["unsupported_changes"]
    )


def _ai_section(explanation: dict[str, Any] | None) -> str:
    if explanation is None:
        return (
            "<p class='muted'>本次分析未启用 AI。确定性 IFC 差分报告仍然完整可用。</p>"
        )
    provider = explanation.get("provider", "deepseek")
    model = explanation.get("model", "unknown")
    content = explanation.get("explanation", explanation)
    return (
        f"<p class='muted'>Provider: {_escape(provider)} · Model: {_escape(model)}</p>"
        f"<pre>{html.escape(json.dumps(content, indent=2, ensure_ascii=False), quote=True)}</pre>"
    )


def build_html_report(
    artifact: dict[str, Any],
    *,
    explanation: dict[str, Any] | None = None,
) -> str:
    """Build one deterministic, offline-viewable HTML report."""
    validate_product_artifact(artifact)
    summary = artifact["summary"]
    unsupported_section = ""
    if artifact["unsupported_changes"]:
        unsupported_section = f"""
        <section>
          <h2>未支持的检测结果</h2>
          <p class="muted">这些 IfcDiff 标志被保留，但没有被包装成受支持的 Change Record。</p>
          <div class="table-wrap"><table>
            <thead><tr><th>GlobalId</th><th>原因</th><th>证据选择器</th></tr></thead>
            <tbody>{_unsupported_rows(artifact)}</tbody>
          </table></div>
        </section>
        """
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BIMChange-Agent 分析报告</title>
  <style>
    :root {{ color-scheme: light; --ink:#18212b; --muted:#65717d; --line:#dce2e8; --panel:#f6f8fa; --accent:#315f72; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; color:var(--ink); background:#eef2f4; font:14px/1.55 "Segoe UI", "Microsoft YaHei", sans-serif; }}
    main {{ width:min(1280px, calc(100% - 40px)); margin:28px auto; }}
    header, section {{ background:white; border:1px solid var(--line); border-radius:14px; padding:24px; margin-bottom:16px; }}
    h1 {{ margin:0 0 8px; font-size:28px; }} h2 {{ margin:0 0 14px; font-size:19px; }}
    .muted {{ color:var(--muted); }}
    .files {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:18px; }}
    .file {{ background:var(--panel); border-radius:10px; padding:13px 15px; }}
    .cards {{ display:grid; grid-template-columns:repeat(5, minmax(120px,1fr)); gap:10px; }}
    .card {{ border:1px solid var(--line); border-radius:11px; padding:15px; }}
    .card strong {{ display:block; font-size:24px; color:var(--accent); }}
    .table-wrap {{ overflow:auto; }} table {{ width:100%; border-collapse:collapse; }}
    th, td {{ padding:10px 11px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    th {{ background:var(--panel); position:sticky; top:0; }} code {{ font-size:12px; }}
    .badge {{ display:inline-block; background:#e7eff2; color:#244c5d; border-radius:999px; padding:2px 8px; }}
    .empty {{ text-align:center; color:var(--muted); padding:28px; }}
    pre {{ white-space:pre-wrap; word-break:break-word; background:var(--panel); border-radius:10px; padding:16px; }}
    footer {{ color:var(--muted); text-align:center; padding:12px; }}
    @media (max-width:800px) {{ .files, .cards {{ grid-template-columns:1fr; }} main {{ width:calc(100% - 20px); }} }}
  </style>
</head>
<body><main>
  <header>
    <h1>BIMChange-Agent 分析报告</h1>
    <p class="muted">受限 IFC4 预览 · 确定性差分为权威数据源 · AI 仅用于可选解释</p>
    <div class="files">
      <div class="file"><strong>旧版本</strong><br>{_escape(artifact['source']['file_name'])}<br><code>{_escape(artifact['source']['sha256'])}</code></div>
      <div class="file"><strong>新版本</strong><br>{_escape(artifact['revised']['file_name'])}<br><code>{_escape(artifact['revised']['sha256'])}</code></div>
    </div>
  </header>
  <section>
    <h2>变更摘要</h2>
    <div class="cards">
      <div class="card">受支持变更<strong>{summary['total_supported']}</strong></div>
      <div class="card">新增<strong>{summary['added']}</strong></div>
      <div class="card">删除<strong>{summary['deleted']}</strong></div>
      <div class="card">属性修改<strong>{summary['property_modified']}</strong></div>
      <div class="card">未支持<strong>{summary['unsupported']}</strong></div>
    </div>
  </section>
  <section>
    <h2>变更明细</h2>
    <div class="table-wrap"><table>
      <thead><tr><th>类型</th><th>实体</th><th>GlobalId</th><th>楼层</th><th>字段</th><th>旧值</th><th>新值</th></tr></thead>
      <tbody>{_change_rows(artifact)}</tbody>
    </table></div>
  </section>
  {unsupported_section}
  <section><h2>AI 解读</h2>{_ai_section(explanation)}</section>
  <section><h2>边界与警告</h2><ul>{_warning_items(artifact)}</ul></section>
  <footer>本报告不能替代专业 BIM 协调、工程审查或结构安全评估。</footer>
</main></body></html>"""


def write_html_report(
    artifact: dict[str, Any],
    output_path: Path,
    *,
    explanation: dict[str, Any] | None = None,
) -> Path:
    """Write a self-contained UTF-8 HTML report and return its absolute path."""
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            build_html_report(artifact, explanation=explanation), encoding="utf-8"
        )
        temporary.replace(output_path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
    return output_path
