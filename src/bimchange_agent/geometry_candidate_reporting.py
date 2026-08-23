"""Deterministic HTML export for the explicit geometry product candidate."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .geometry_product_candidate import validate_candidate_artifact


TEXT = {
    "en": {
        "lang": "en",
        "title": "BIMChange-Agent geometry candidate report",
        "subtitle": "Candidate scope: placement-only translation · deterministic evidence",
        "source": "Previous version",
        "revised": "Revised version",
        "summary": "Change summary",
        "geometry": "Geometry changes",
        "unsupported": "Unsupported detections",
        "details": "Change details",
        "entity": "Entity",
        "storey": "Storey",
        "semantic": "Geometry semantic",
        "old": "Previous world origin (m)",
        "new": "Revised world origin (m)",
        "delta": "Delta (m)",
        "distance": "Distance (m)",
        "reason": "Reason",
        "selector": "Evidence selector",
        "warnings": "Boundaries and warnings",
        "none": "No supported placement translation was detected.",
    },
    "zh_CN": {
        "lang": "zh-CN",
        "title": "BIMChange-Agent 几何候选报告",
        "subtitle": "候选范围：仅放置平移 · 确定性证据",
        "source": "旧版本",
        "revised": "新版本",
        "summary": "变更摘要",
        "geometry": "几何变化",
        "unsupported": "未支持检测",
        "details": "变更明细",
        "entity": "实体",
        "storey": "楼层",
        "semantic": "几何语义",
        "old": "旧世界原点（米）",
        "new": "新世界原点（米）",
        "delta": "位移向量（米）",
        "distance": "位移距离（米）",
        "reason": "原因",
        "selector": "证据选择器",
        "warnings": "边界与警告",
        "none": "没有检测到受支持的放置平移。",
    },
}


def _text(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (dict, list, bool, int, float)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _escape(value: Any) -> str:
    return html.escape(_text(value), quote=True)


def build_geometry_candidate_html(
    artifact: dict[str, Any], *, language: str = "zh_CN"
) -> str:
    """Build one deterministic, offline candidate report."""
    validate_candidate_artifact(artifact)
    labels = TEXT.get(language, TEXT["zh_CN"])
    rows: list[str] = []
    for record in artifact["changes"]:
        geometry = record["geometry_change"]
        if geometry is None:
            semantic = "—"
            old_origin = record["old_value"]
            new_origin = record["new_value"]
            delta = "—"
            distance = "—"
        else:
            semantic = geometry["subtype"]
            old_origin = geometry["old_origin"]
            new_origin = geometry["new_origin"]
            delta = geometry["delta"]
            distance = geometry["distance"]
        storey = record["location"]["building_storey"]
        rows.append(
            "<tr>"
            f"<td>{_escape(record['change_type'])}</td>"
            f"<td>{_escape(record['entity_type'])}<br><code>{_escape(record['global_id'])}</code></td>"
            f"<td>{_escape(storey['name'] if storey else None)}</td>"
            f"<td>{_escape(semantic)}</td>"
            f"<td>{_escape(old_origin)}</td>"
            f"<td>{_escape(new_origin)}</td>"
            f"<td>{_escape(delta)}</td>"
            f"<td>{_escape(distance)}</td>"
            "</tr>"
        )
    if not rows:
        rows.append(f"<tr><td colspan='8' class='empty'>{labels['none']}</td></tr>")
    unsupported_rows = "".join(
        "<tr>"
        f"<td><code>{_escape(item['global_id'])}</code></td>"
        f"<td>{_escape(item['reason'])}</td>"
        f"<td><code>{_escape(item['selector'])}</code></td>"
        "</tr>"
        for item in artifact["unsupported_changes"]
    )
    unsupported_section = ""
    if unsupported_rows:
        unsupported_section = (
            f"<section><h2>{labels['unsupported']}</h2><div class='table-wrap'><table>"
            f"<thead><tr><th>GlobalId</th><th>{labels['reason']}</th><th>{labels['selector']}</th></tr></thead>"
            f"<tbody>{unsupported_rows}</tbody></table></div></section>"
        )
    warnings = "".join(f"<li>{_escape(item)}</li>" for item in artifact["warnings"])
    summary = artifact["summary"]
    return f"""<!doctype html>
<html lang="{labels['lang']}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{labels['title']}</title>
<style>
:root{{--ink:#202327;--muted:#687078;--line:#d4d2cc;--panel:#fbfaf7;--accent:#8e4e36;--canvas:#f2f1ed}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--canvas);color:var(--ink);font:14px/1.55 "Segoe UI",sans-serif}}
main{{width:min(1320px,calc(100% - 32px));margin:24px auto}} section,header{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:22px;margin-bottom:14px}}
h1{{margin:0 0 6px;font-size:27px}} h2{{margin:0 0 12px;font-size:18px}} .muted{{color:var(--muted)}}
.files,.cards{{display:grid;grid-template-columns:1fr 1fr;gap:10px}} .file,.card{{border:1px solid var(--line);border-radius:9px;padding:12px}}
.card strong{{display:block;color:var(--accent);font-size:24px}} .table-wrap{{overflow:auto}} table{{width:100%;border-collapse:collapse}}
th,td{{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}} th{{background:#f5f2ec}} code{{font-size:12px}}
.empty{{text-align:center;color:var(--muted);padding:24px}} @media(max-width:760px){{.files,.cards{{grid-template-columns:1fr}}}}
</style></head><body><main>
<header><h1>{labels['title']}</h1><p class="muted">{labels['subtitle']}</p>
<div class="files"><div class="file"><strong>{labels['source']}</strong><br>{_escape(artifact['source']['file_name'])}<br><code>{_escape(artifact['source']['sha256'])}</code></div>
<div class="file"><strong>{labels['revised']}</strong><br>{_escape(artifact['revised']['file_name'])}<br><code>{_escape(artifact['revised']['sha256'])}</code></div></div></header>
<section><h2>{labels['summary']}</h2><div class="cards"><div class="card">{labels['geometry']}<strong>{summary['geometry_modified']}</strong></div><div class="card">{labels['unsupported']}<strong>{summary['unsupported']}</strong></div></div></section>
<section><h2>{labels['details']}</h2><div class="table-wrap"><table><thead><tr><th>Type</th><th>{labels['entity']}</th><th>{labels['storey']}</th><th>{labels['semantic']}</th><th>{labels['old']}</th><th>{labels['new']}</th><th>{labels['delta']}</th><th>{labels['distance']}</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>
{unsupported_section}<section><h2>{labels['warnings']}</h2><ul>{warnings}</ul></section>
</main></body></html>"""


def write_geometry_candidate_html(
    artifact: dict[str, Any], output_path: Path, *, language: str = "zh_CN"
) -> Path:
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            build_geometry_candidate_html(artifact, language=language),
            encoding="utf-8",
        )
        temporary.replace(output_path)
    finally:
        temporary.unlink(missing_ok=True)
    return output_path
