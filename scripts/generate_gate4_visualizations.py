"""Generate and verify deterministic Gate 4 research visualizations.

The frozen machine-readable offline summary is the sole numeric source. SVG is
the canonical deterministic output; PNG is a convenience derivative rendered
from the same scene graph with Pillow.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = (
    REPOSITORY_ROOT
    / "evals"
    / "results"
    / "held_out"
    / "gate4-controlled-heldout-v0.1.0"
)
SUMMARY_PATH = DATASET_DIR / "gate4-offline-summary.json"
VALIDATION_PATH = DATASET_DIR / "gate4-independent-validation.json"
OUTPUT_DIR = REPOSITORY_ROOT / "docs" / "assets" / "gate4"
MANIFEST_PATH = OUTPUT_DIR / "chart-manifest.json"

INK = "#2D302F"
MUTED = "#717572"
GRID = "#DDDFDC"
PAPER = "#FDFDFC"
PANEL = "#F4F4F2"
STONE = "#858985"
STONE_LIGHT = "#E7E8E5"
SAGE = "#6F7872"
SAGE_LIGHT = "#DFE2DE"
OCHRE = "#918674"
OCHRE_LIGHT = "#E9E5DE"
CLAY = "#88746A"
CLAY_LIGHT = "#E7E1DE"
MOSS = "#777D73"
TAUPE = "#858079"
DIRECT = STONE
TOOL = SAGE
PROPOSED = CLAY

WORKFLOWS = ["direct_llm", "tool_using_agent", "proposed"]
WORKFLOW_LABELS = {
    "direct_llm": "Direct LLM",
    "tool_using_agent": "Tool-Using Agent",
    "proposed": "Proposed",
}
WORKFLOW_LABELS_BILINGUAL = {
    "direct_llm": "Direct LLM / 直接模型",
    "tool_using_agent": "Tool-Using Agent / 工具型智能体",
    "proposed": "Proposed / 本方法",
}
WORKFLOW_COLORS = {
    "direct_llm": DIRECT,
    "tool_using_agent": TOOL,
    "proposed": PROPOSED,
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def artifact_sha256_file(path: Path) -> str:
    """Return the repository's Git-normalized artifact hash."""
    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"Expected JSON object: {path}")
    return value


def pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%"


@dataclass
class Scene:
    width: int
    height: int
    operations: list[dict[str, Any]] = field(default_factory=list)

    def rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        *,
        fill: str = "none",
        stroke: str = "none",
        stroke_width: float = 0,
        radius: float = 0,
    ) -> None:
        self.operations.append(
            {
                "kind": "rect",
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "fill": fill,
                "stroke": stroke,
                "stroke_width": stroke_width,
                "radius": radius,
            }
        )

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        stroke: str = INK,
        stroke_width: float = 2,
        dash: str | None = None,
    ) -> None:
        self.operations.append(
            {
                "kind": "line",
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "stroke": stroke,
                "stroke_width": stroke_width,
                "dash": dash,
            }
        )

    def circle(
        self,
        x: float,
        y: float,
        radius: float,
        *,
        fill: str,
        stroke: str = "none",
        stroke_width: float = 0,
    ) -> None:
        self.operations.append(
            {
                "kind": "circle",
                "x": x,
                "y": y,
                "radius": radius,
                "fill": fill,
                "stroke": stroke,
                "stroke_width": stroke_width,
            }
        )

    def polygon(
        self,
        points: list[tuple[float, float]],
        *,
        fill: str,
        stroke: str = "none",
        stroke_width: float = 0,
    ) -> None:
        self.operations.append(
            {
                "kind": "polygon",
                "points": points,
                "fill": fill,
                "stroke": stroke,
                "stroke_width": stroke_width,
            }
        )

    def text(
        self,
        x: float,
        y: float,
        value: str,
        *,
        size: int = 24,
        fill: str = INK,
        anchor: str = "start",
        weight: str = "regular",
        family: str = "sans",
        valign: str = "top",
    ) -> None:
        self.operations.append(
            {
                "kind": "text",
                "x": x,
                "y": y,
                "value": value,
                "size": size,
                "fill": fill,
                "anchor": anchor,
                "weight": weight,
                "family": family,
                "valign": valign,
            }
        )

    def svg_bytes(self) -> bytes:
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" '
                f'width="{self.width}" height="{self.height}" '
                f'viewBox="0 0 {self.width} {self.height}" role="img">'
            ),
            f'<rect width="{self.width}" height="{self.height}" fill="{PAPER}"/>',
        ]
        for op in self.operations:
            kind = op["kind"]
            if kind == "rect":
                lines.append(
                    f'<rect x="{op["x"]}" y="{op["y"]}" '
                    f'width="{op["width"]}" height="{op["height"]}" '
                    f'rx="{op["radius"]}" fill="{op["fill"]}" '
                    f'stroke="{op["stroke"]}" stroke-width="{op["stroke_width"]}"/>'
                )
            elif kind == "line":
                dash = (
                    f' stroke-dasharray="{op["dash"]}"' if op["dash"] else ""
                )
                lines.append(
                    f'<line x1="{op["x1"]}" y1="{op["y1"]}" '
                    f'x2="{op["x2"]}" y2="{op["y2"]}" '
                    f'stroke="{op["stroke"]}" stroke-width="{op["stroke_width"]}"'
                    f'{dash}/>'
                )
            elif kind == "circle":
                lines.append(
                    f'<circle cx="{op["x"]}" cy="{op["y"]}" r="{op["radius"]}" '
                    f'fill="{op["fill"]}" stroke="{op["stroke"]}" '
                    f'stroke-width="{op["stroke_width"]}"/>'
                )
            elif kind == "polygon":
                points = " ".join(f"{x},{y}" for x, y in op["points"])
                lines.append(
                    f'<polygon points="{points}" fill="{op["fill"]}" '
                    f'stroke="{op["stroke"]}" stroke-width="{op["stroke_width"]}"/>'
                )
            elif kind == "text":
                family = (
                    "ui-monospace, SFMono-Regular, Consolas, monospace"
                    if op["family"] == "mono"
                    else "Inter, Microsoft YaHei, Noto Sans CJK SC, Segoe UI, Arial, sans-serif"
                )
                lines.append(
                    f'<text x="{op["x"]}" y="{op["y"]}" '
                    f'fill="{op["fill"]}" font-size="{op["size"]}" '
                    f'font-family="{family}" font-weight="{700 if op["weight"] == "bold" else 400}" '
                    f'text-anchor="{op["anchor"]}" '
                    f'dominant-baseline="{"central" if op["valign"] == "middle" else "hanging"}">'
                    f'{html.escape(op["value"])}</text>'
                )
        lines.append("</svg>")
        return ("\n".join(lines) + "\n").encode("utf-8")

    def png_bytes(self) -> bytes:
        image = Image.new("RGB", (self.width, self.height), PAPER)
        draw = ImageDraw.Draw(image)
        for op in self.operations:
            kind = op["kind"]
            if kind == "rect":
                xy = (
                    round(op["x"]),
                    round(op["y"]),
                    round(op["x"] + op["width"]),
                    round(op["y"] + op["height"]),
                )
                kwargs: dict[str, Any] = {}
                if op["fill"] != "none":
                    kwargs["fill"] = op["fill"]
                if op["stroke"] != "none":
                    kwargs["outline"] = op["stroke"]
                    kwargs["width"] = max(1, round(op["stroke_width"]))
                draw.rounded_rectangle(xy, radius=round(op["radius"]), **kwargs)
            elif kind == "line":
                draw.line(
                    (op["x1"], op["y1"], op["x2"], op["y2"]),
                    fill=op["stroke"],
                    width=max(1, round(op["stroke_width"])),
                )
            elif kind == "circle":
                r = op["radius"]
                xy = (op["x"] - r, op["y"] - r, op["x"] + r, op["y"] + r)
                draw.ellipse(
                    xy,
                    fill=None if op["fill"] == "none" else op["fill"],
                    outline=None if op["stroke"] == "none" else op["stroke"],
                    width=max(1, round(op["stroke_width"])),
                )
            elif kind == "polygon":
                draw.polygon(
                    op["points"],
                    fill=None if op["fill"] == "none" else op["fill"],
                    outline=None if op["stroke"] == "none" else op["stroke"],
                )
            elif kind == "text":
                font = load_font(op["size"], op["weight"], op["family"])
                anchor = {
                    ("start", "top"): "lt",
                    ("middle", "top"): "mt",
                    ("end", "top"): "rt",
                    ("start", "middle"): "lm",
                    ("middle", "middle"): "mm",
                    ("end", "middle"): "rm",
                }[(op["anchor"], op["valign"])]
                draw.text(
                    (op["x"], op["y"]),
                    op["value"],
                    fill=op["fill"],
                    font=font,
                    anchor=anchor,
                )
        from io import BytesIO

        buffer = BytesIO()
        image.save(buffer, format="PNG", compress_level=9, optimize=False)
        return buffer.getvalue()


def load_font(size: int, weight: str, family: str) -> ImageFont.FreeTypeFont:
    if family == "mono":
        candidates = ["C:/Windows/Fonts/consola.ttf", "DejaVuSansMono.ttf"]
    elif weight == "bold":
        candidates = [
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/seguisb.ttf",
            "DejaVuSans-Bold.ttf",
        ]
    else:
        candidates = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/segoeui.ttf",
            "DejaVuSans.ttf",
        ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    raise RuntimeError("No suitable TrueType font found for PNG rendering")


def add_research_header(scene: Scene, title: str, subtitle: str) -> None:
    scene.text(70, 42, title, size=36, weight="bold")
    scene.text(70, 92, subtitle, size=20, fill=MUTED)
    cx, cy = scene.width - 78, 61
    for dx, dy, color in [
        (0, -11, SAGE),
        (10, -3, OCHRE),
        (6, 9, CLAY),
        (-6, 9, MOSS),
        (-10, -3, TAUPE),
    ]:
        scene.circle(cx + dx, cy + dy, 5, fill=color)
    scene.circle(cx, cy, 4, fill=INK)
    scene.line(70, 136, scene.width - 70, 136, stroke=GRID, stroke_width=2)


def add_footer(scene: Scene, source: str) -> None:
    scene.line(70, scene.height - 64, scene.width - 70, scene.height - 64, stroke=GRID)
    scene.text(
        70,
        scene.height - 48,
        "BIMChange-Agent v0.1.0 · frozen Gate 4 data / Gate 4 冻结数据",
        size=15,
        fill=MUTED,
    )
    scene.text(
        scene.width - 70,
        scene.height - 48,
        source,
        size=15,
        fill=MUTED,
        anchor="end",
        family="mono",
    )


def add_percent_axis(
    scene: Scene,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    *,
    step: int = 20,
) -> None:
    for tick in range(0, 101, step):
        x = x0 + (x1 - x0) * tick / 100
        scene.line(x, y0, x, y1, stroke=GRID, stroke_width=1)
        scene.text(x, y1 + 12, f"{tick}%", size=16, fill=MUTED, anchor="middle")


def workflow_overview(summary: dict[str, Any]) -> Scene:
    scene = Scene(1500, 820)
    add_research_header(
        scene,
        "Gate 4 workflow performance / Gate 4 工作流表现",
        "120 scheduled executions per workflow · controlled synthetic IFC4 fixture / 每种工作流 120 次计划执行 · 受控合成 IFC4 样例",
    )
    metrics = [
        ("Semantic exact match", "语义精确匹配", "semantic_exact_match_accuracy"),
        ("Change F1", "变更 F1", "change_f1"),
        ("Deterministic evidence support", "确定性证据支持", "evidence_support_rate"),
    ]
    x0, x1, value_x = 390, 1210, 1410
    y0, y1 = 196, 680
    add_percent_axis(scene, x0, x1, y0, y1)
    group_height = 152
    bar_height = 29
    for metric_index, (label_en, label_zh, key) in enumerate(metrics):
        group_y = y0 + metric_index * group_height
        scene.text(70, group_y + 25, label_en, size=17, weight="bold")
        scene.text(70, group_y + 50, label_zh, size=16, fill=MUTED)
        for workflow_index, workflow in enumerate(WORKFLOWS):
            y = group_y + workflow_index * 38
            value = float(summary["overall_by_workflow"][workflow][key])
            scene.rect(x0, y, (x1 - x0) * value, bar_height, fill=WORKFLOW_COLORS[workflow], radius=1)
            scene.text(x0 + 12, y + 5, WORKFLOW_LABELS_BILINGUAL[workflow], size=13, fill=PAPER, weight="bold")
            scene.text(
                value_x,
                y + 5,
                pct(value, 2),
                size=16,
                fill=INK,
                family="mono",
                anchor="end",
            )
    add_footer(scene, "gate4-offline-summary.json / overall_by_workflow")
    return scene


def heat_color(value: float) -> str:
    stops = [
        (0.0, "#F1F1EF"),
        (0.25, "#DFE1DD"),
        (0.5, "#C0C5C0"),
        (0.75, "#939C95"),
        (1.0, "#626A64"),
    ]
    for index in range(len(stops) - 1):
        left_value, left_color = stops[index]
        right_value, right_color = stops[index + 1]
        if value <= right_value:
            ratio = (value - left_value) / (right_value - left_value)
            left = tuple(int(left_color[i : i + 2], 16) for i in (1, 3, 5))
            right = tuple(int(right_color[i : i + 2], 16) for i in (1, 3, 5))
            rgb = tuple(round(a + (b - a) * ratio) for a, b in zip(left, right))
            return "#" + "".join(f"{component:02X}" for component in rgb)
    return stops[-1][1]


def category_heatmap(summary: dict[str, Any]) -> Scene:
    scene = Scene(1580, 840)
    add_research_header(
        scene,
        "Semantic exact match by question category / 各问题类别语义精确匹配率",
        "Three-repetition aggregate; descriptive cuts, not independent experiments / 三次重复汇总；仅作描述性切分",
    )
    categories = [
        ("evidence_boundary", "Evidence boundary / 证据边界"),
        ("fact_lookup", "Fact lookup / 事实查询"),
        ("filtered_lookup", "Filtered lookup / 条件查询"),
        ("negative_control", "Negative control / 负向对照"),
        ("property_change", "Property change / 属性变更"),
        ("summary", "Summary / 汇总"),
    ]
    x0, cell_width = 540, 320
    y0, cell_height = 215, 76
    for index, workflow in enumerate(WORKFLOWS):
        scene.text(
            x0 + index * cell_width + cell_width / 2,
            169,
            WORKFLOW_LABELS_BILINGUAL[workflow],
            size=16,
            weight="bold",
            anchor="middle",
        )
    for row, (category, label) in enumerate(categories):
        y = y0 + row * cell_height
        scene.text(70, y + 20, label, size=19, weight="bold")
        for column, workflow in enumerate(WORKFLOWS):
            x = x0 + column * cell_width
            value = float(summary["per_category"][workflow][category]["semantic_exact_match_accuracy"])
            fill = heat_color(value)
            scene.rect(x, y, cell_width - 12, cell_height - 10, fill=fill, radius=1)
            scene.text(
                x + (cell_width - 10) / 2,
                y + 18,
                pct(value, 2),
                size=22,
                fill=PAPER if value >= 0.68 else INK,
                weight="bold",
                family="mono",
                anchor="middle",
            )
    add_footer(scene, "gate4-offline-summary.json / per_category")
    return scene


def repeatability(summary: dict[str, Any]) -> Scene:
    scene = Scene(1500, 670)
    add_research_header(
        scene,
        "Question-level exact-match repeatability / 问题级精确匹配可重复性",
        "40 held-out questions grouped by exact successes across three repetitions / 40 道留出问题按三次重复中的成功次数分组",
    )
    colors = [STONE, OCHRE, SAGE, CLAY]
    labels = ["0 of 3 / 3次中0次", "1 of 3 / 3次中1次", "2 of 3 / 3次中2次", "3 of 3 / 3次中3次"]
    x0, x1 = 440, 1390
    y0 = 230
    for workflow_index, workflow in enumerate(WORKFLOWS):
        y = y0 + workflow_index * 105
        scene.text(70, y + 21, WORKFLOW_LABELS_BILINGUAL[workflow], size=18, weight="bold")
        distribution = summary["question_success_frequency"][workflow]["frequency_distribution"]
        cursor = x0
        for count_index in range(4):
            count = int(distribution[str(count_index)])
            width = (x1 - x0) * count / 40
            scene.rect(cursor, y, width, 62, fill=colors[count_index])
            if width >= 22:
                scene.text(
                    cursor + width / 2,
                    y + (19 if width >= 50 else 21),
                    str(count),
                    size=20 if width >= 50 else 15,
                    fill=PAPER if count_index in (0, 2, 3) else INK,
                    weight="bold",
                    family="mono",
                    anchor="middle",
                )
            cursor += width
    legend_x = 330
    for index, label in enumerate(labels):
        x = legend_x + index * 225
        scene.rect(x, 560, 22, 22, fill=colors[index], radius=3)
        scene.text(x + 32, 559, label, size=14, fill=MUTED)
    add_footer(scene, "gate4-offline-summary.json / question_success_frequency")
    return scene


def repetition_stability(summary: dict[str, Any]) -> Scene:
    scene = Scene(1700, 900)
    add_research_header(
        scene,
        "Run-to-run variation across three repetitions / 三次重复的运行间变异",
        "Dots: repetitions · diamonds: means · lines: observed ranges / 圆点：重复 · 菱形：均值 · 横线：观测范围",
    )
    panels = [
        ("Semantic exact match / 语义精确匹配", "semantic_exact_match_accuracy", 360, 780, 45.0, 100.0, 900),
        ("Change F1 / 变更 F1", "change_f1", 1090, 1510, 50.0, 100.0, 1630),
    ]
    for title, key, x0, x1, minimum, maximum, value_x in panels:
        scene.text((x0 + x1) / 2, 170, title, size=22, weight="bold", anchor="middle")
        for tick in range(50, 101, 10):
            x = x0 + (x1 - x0) * (tick - minimum) / (maximum - minimum)
            scene.line(x, 220, x, 720, stroke=GRID)
            scene.text(x, 736, f"{tick}%", size=15, fill=MUTED, anchor="middle")
        scene.text(value_x, 200, "Mean / 均值", size=14, fill=MUTED, anchor="end")
        for row, workflow in enumerate(WORKFLOWS):
            y = 300 + row * 145
            if x0 < 500:
                scene.text(70, y - 11, WORKFLOW_LABELS_BILINGUAL[workflow], size=17, weight="bold")
            repetitions = summary["repetition"][workflow]["per_repetition"]
            values = [float(item["metrics"][key]) for item in repetitions]
            mean = float(summary["repetition"][workflow]["across_repetition_summary"][key]["mean"])
            scale = lambda value: x0 + (x1 - x0) * (value * 100 - minimum) / (maximum - minimum)
            scene.line(scale(min(values)), y, scale(max(values)), y, stroke=WORKFLOW_COLORS[workflow], stroke_width=5)
            mx = scale(mean)
            scene.polygon(
                [(mx, y - 15), (mx + 12, y), (mx, y + 15), (mx - 12, y)],
                fill=WORKFLOW_COLORS[workflow],
            )
            for index, value in enumerate(values, start=1):
                point_y = y + 18 + index * 18
                scene.circle(scale(value), point_y, 9, fill=PAPER, stroke=WORKFLOW_COLORS[workflow], stroke_width=3)
                scene.text(
                    scale(value),
                    point_y,
                    str(index),
                    size=10,
                    fill=INK,
                    weight="bold",
                    family="mono",
                    anchor="middle",
                    valign="middle",
                )
            scene.text(value_x, y - 11, pct(mean, 2), size=16, family="mono", anchor="end")
    add_footer(scene, "gate4-offline-summary.json / repetition")
    return scene


def bootstrap_forest(summary: dict[str, Any]) -> Scene:
    scene = Scene(1600, 760)
    add_research_header(
        scene,
        "Question-clustered paired bootstrap contrasts / 问题聚类配对 Bootstrap 对比",
        "Proposed minus comparator · 2,000 resamples · seed 20260808 · percentage points / 本方法减对照 · 百分点",
    )
    rows = [
        ("Exact match", "direct_llm_minus_proposed", "Direct LLM"),
        ("Change F1", "direct_llm_minus_proposed", "Direct LLM"),
        ("Exact match", "tool_using_agent_minus_proposed", "Tool-Using Agent"),
        ("Change F1", "tool_using_agent_minus_proposed", "Tool-Using Agent"),
    ]
    metric_keys = {"Exact match": "semantic_exact_match_accuracy", "Change F1": "change_f1"}
    x0, x1, value_x = 500, 1190, 1510
    minimum, maximum = -5.0, 60.0
    scale = lambda value: x0 + (x1 - x0) * (value - minimum) / (maximum - minimum)
    for tick in range(0, 61, 10):
        x = scale(float(tick))
        scene.line(x, 200, x, 630, stroke=INK if tick == 0 else GRID, stroke_width=2 if tick == 0 else 1)
        scene.text(x, 644, f"{tick:+d}", size=15, fill=MUTED, anchor="middle", family="mono")
    for row_index, (metric_label, pair_key, comparator) in enumerate(rows):
        y = 245 + row_index * 92
        source = summary["uncertainty"]["pairs"][pair_key][metric_keys[metric_label]]
        point = -float(source["point_difference_left_minus_right"]) * 100
        lower, upper = [-float(value) * 100 for value in reversed(source["percentile_95_interval"])]
        comparator_zh = "直接模型" if comparator == "Direct LLM" else "工具型智能体"
        metric_zh = "精确匹配" if metric_label == "Exact match" else "变更 F1"
        scene.text(70, y - 22, f"Proposed − {comparator} / 本方法 − {comparator_zh}", size=16, weight="bold")
        scene.text(70, y + 7, f"{metric_label} / {metric_zh}", size=15, fill=MUTED)
        color = PROPOSED if comparator == "Direct LLM" else TOOL
        scene.line(scale(lower), y, scale(upper), y, stroke=color, stroke_width=5)
        scene.line(scale(lower), y - 11, scale(lower), y + 11, stroke=color, stroke_width=3)
        scene.line(scale(upper), y - 11, scale(upper), y + 11, stroke=color, stroke_width=3)
        scene.circle(scale(point), y, 11, fill=color, stroke=PAPER, stroke_width=2)
        scene.text(
            value_x,
            y - 11,
            f"{point:+.2f} pp [{lower:+.2f}, {upper:+.2f}]",
            size=15,
            fill=INK,
            family="mono",
            anchor="end",
        )
    add_footer(scene, "gate4-offline-summary.json / uncertainty")
    return scene


def manual_audit(summary: dict[str, Any]) -> Scene:
    scene = Scene(1900, 760)
    add_research_header(
        scene,
        "Blinded manual audit / 盲法人工审计",
        "One reviewer · 135 sampled executions · 505 atomic claims / 1 名审阅者 · 135 次抽样执行 · 505 条原子声明",
    )
    panels = [
        ("Citation verification / 引用核验", "citation", 360, 720, 890),
        ("Exceptional claims / 异常声明", "claims", 1210, 1570, 1830),
    ]
    for title, mode, x0, x1, value_x in panels:
        scene.text((x0 + x1) / 2, 176, title, size=20, weight="bold", anchor="middle")
        maximum = 100.0 if mode == "citation" else 2.0
        for tick in range(0, 5):
            value = maximum * tick / 4
            x = x0 + (x1 - x0) * tick / 4
            scene.line(x, 225, x, 590, stroke=GRID)
            scene.text(x, 606, f"{value:.1f}%", size=14, fill=MUTED, anchor="middle")
        for row, workflow in enumerate(WORKFLOWS):
            y = 270 + row * 105
            item = summary["manual_audit"]["by_workflow"][workflow]
            if mode == "citation":
                numerator = int(item["evidence_references_verified_count"])
                denominator = int(item["audited_candidate_count"])
                value = numerator / denominator * 100
            else:
                labels = item["claim_label_counts"]
                numerator = int(labels.get("unsupported", 0)) + int(labels.get("indeterminate", 0))
                denominator = int(item["atomic_claim_count"])
                value = numerator / denominator * 100
            width = (x1 - x0) * value / maximum
            scene.rect(x0, y, width, 42, fill=WORKFLOW_COLORS[workflow], radius=1)
            scene.text(x0 - 18, y + 8, WORKFLOW_LABELS_BILINGUAL[workflow], size=14, anchor="end")
            scene.text(
                value_x,
                y + 8,
                f"{numerator}/{denominator} · {value:.2f}%",
                size=15,
                family="mono",
                anchor="end",
            )
    add_footer(scene, "gate4-offline-summary.json / manual_audit")
    return scene


def validate_sources(summary: dict[str, Any], validation: dict[str, Any]) -> None:
    if validation["status"] != "PASS_WITH_RECORDED_DATA_LIMITATIONS":
        raise ValueError("Independent validation status is not the frozen PASS status")
    expected_sha = validation["validated_artifacts"]["summary"]["sha256"]
    actual_sha = artifact_sha256_file(SUMMARY_PATH)
    if actual_sha != expected_sha:
        raise ValueError("Offline summary SHA-256 does not match independent validation")
    if sum(int(summary["overall_by_workflow"][key]["execution_count"]) for key in WORKFLOWS) != 360:
        raise ValueError("Expected exactly 360 scheduled primary executions")
    for workflow in WORKFLOWS:
        overall = summary["overall_by_workflow"][workflow]
        if int(overall["execution_count"]) != 120:
            raise ValueError(f"Expected 120 executions for {workflow}")
        distribution = summary["question_success_frequency"][workflow]["frequency_distribution"]
        if sum(int(distribution[str(index)]) for index in range(4)) != 40:
            raise ValueError(f"Exact-success distribution does not sum to 40 for {workflow}")
    uncertainty = summary["uncertainty"]
    if uncertainty["seed"] != 20260808 or uncertainty["resamples"] != 2000:
        raise ValueError("Bootstrap seed or resample count changed")
    audit = summary["manual_audit"]["overall"]
    if int(audit["atomic_claim_count"]) != 505 or int(audit["audited_execution_count"]) != 135:
        raise ValueError("Manual-audit frozen counts changed")


def chart_specs(summary: dict[str, Any]) -> list[tuple[str, Scene, dict[str, Any]]]:
    return [
        (
            "workflow-performance",
            workflow_overview(summary),
            {
                "question": "How do the three workflows compare on structured accuracy and evidence support?",
                "family": "comparison",
                "variant": "grouped horizontal bar",
                "source_fields": [
                    "overall_by_workflow.*.semantic_exact_match_accuracy",
                    "overall_by_workflow.*.change_f1",
                    "overall_by_workflow.*.evidence_support_rate",
                ],
                "readme": True,
            },
        ),
        (
            "category-exact-match",
            category_heatmap(summary),
            {
                "question": "Where does exact-match performance vary across the frozen question taxonomy?",
                "family": "matrix and cohort",
                "variant": "annotated heatmap",
                "source_fields": ["per_category.*.*.semantic_exact_match_accuracy"],
                "readme": True,
            },
        ),
        (
            "question-repeatability",
            repeatability(summary),
            {
                "question": "How consistently does each workflow answer the same questions exactly across repetitions?",
                "family": "composition",
                "variant": "100% stacked bar with counts",
                "source_fields": ["question_success_frequency.*.frequency_distribution"],
                "readme": False,
            },
        ),
        (
            "repetition-stability",
            repetition_stability(summary),
            {
                "question": "What run-to-run variation remains across the three repetition blocks?",
                "family": "uncertainty and benchmark",
                "variant": "dot and observed-range plot",
                "source_fields": ["repetition.*.per_repetition", "repetition.*.across_repetition_summary"],
                "readme": False,
            },
        ),
        (
            "bootstrap-contrasts",
            bootstrap_forest(summary),
            {
                "question": "What uncertainty surrounds Proposed's exact-match and F1 differences on this fixture?",
                "family": "uncertainty and benchmark",
                "variant": "paired-bootstrap forest plot",
                "source_fields": ["uncertainty.pairs.*.semantic_exact_match_accuracy", "uncertainty.pairs.*.change_f1"],
                "transformation": "Signs are inverted from source left-minus-Proposed contrasts to display Proposed-minus-comparator.",
                "readme": False,
            },
        ),
        (
            "manual-audit",
            manual_audit(summary),
            {
                "question": "How do human citation verification and claim-level exceptions differ by workflow?",
                "family": "comparison",
                "variant": "two-panel horizontal bar",
                "source_fields": ["manual_audit.by_workflow"],
                "readme": False,
            },
        ),
    ]


def write_outputs(summary: dict[str, Any], validation: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    chart_entries: list[dict[str, Any]] = []
    for slug, scene, spec in chart_specs(summary):
        svg_path = OUTPUT_DIR / f"{slug}.svg"
        png_path = OUTPUT_DIR / f"{slug}.png"
        svg_path.write_bytes(scene.svg_bytes())
        png_path.write_bytes(scene.png_bytes())
        chart_entries.append(
            {
                "id": slug,
                **spec,
                "dimensions": {"width": scene.width, "height": scene.height},
                "outputs": {
                    "svg": {
                        "path": svg_path.relative_to(REPOSITORY_ROOT).as_posix(),
                        "sha256": sha256_file(svg_path),
                    },
                    "png": {
                        "path": png_path.relative_to(REPOSITORY_ROOT).as_posix(),
                        "sha256": sha256_file(png_path),
                    },
                },
            }
        )
    manifest = {
        "schema_version": "0.1.0",
        "dataset_id": summary["dataset_id"],
        "canonical_numeric_source": SUMMARY_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
        "canonical_numeric_source_sha256": artifact_sha256_file(SUMMARY_PATH),
        "independent_validation_source": VALIDATION_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
        "independent_validation_status": validation["status"],
        "model_calls_made": 0,
        "canonical_format": "SVG",
        "png_role": "convenience derivative rendered from the same scene graph",
        "charts": chart_entries,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def check_outputs(summary: dict[str, Any], validation: dict[str, Any]) -> None:
    manifest = load_json(MANIFEST_PATH)
    if manifest["canonical_numeric_source_sha256"] != artifact_sha256_file(SUMMARY_PATH):
        raise ValueError("Chart manifest points to a different numeric source")
    entries = {entry["id"]: entry for entry in manifest["charts"]}
    for slug, scene, _spec in chart_specs(summary):
        entry = entries[slug]
        svg_path = REPOSITORY_ROOT / entry["outputs"]["svg"]["path"]
        png_path = REPOSITORY_ROOT / entry["outputs"]["png"]["path"]
        if svg_path.read_bytes() != scene.svg_bytes():
            raise ValueError(f"Canonical SVG is stale or non-deterministic: {slug}")
        if sha256_file(svg_path) != entry["outputs"]["svg"]["sha256"]:
            raise ValueError(f"SVG hash mismatch: {slug}")
        if sha256_file(png_path) != entry["outputs"]["png"]["sha256"]:
            raise ValueError(f"PNG hash mismatch: {slug}")
        with Image.open(png_path) as image:
            expected = entry["dimensions"]
            if image.size != (expected["width"], expected["height"]):
                raise ValueError(f"PNG dimensions mismatch: {slug}")
    print(
        json.dumps(
            {
                "status": "PASS",
                "dataset_id": summary["dataset_id"],
                "chart_count": len(entries),
                "canonical_svg_regeneration": "byte-identical",
                "independent_validation_status": validation["status"],
                "model_calls_made": 0,
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--write", action="store_true", help="Write SVG, PNG, and manifest outputs")
    action.add_argument("--check", action="store_true", help="Verify committed outputs against frozen data")
    args = parser.parse_args()

    summary = load_json(SUMMARY_PATH)
    validation = load_json(VALIDATION_PATH)
    validate_sources(summary, validation)
    if args.check:
        check_outputs(summary, validation)
    else:
        write_outputs(summary, validation)
        check_outputs(summary, validation)


if __name__ == "__main__":
    main()
