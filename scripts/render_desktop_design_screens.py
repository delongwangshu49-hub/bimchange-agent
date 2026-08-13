"""Render desktop design states with synthetic records and no IFC or API access."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.desktop_app import (  # noqa: E402
    AISettingsDialog,
    DesktopPreferences,
    MainWindow,
)


def synthetic_artifact() -> dict[str, object]:
    changes = [
        {
            "change_type": "added",
            "entity_type": "IfcBeam",
            "global_id": "SYNTHETIC-BEAM-001",
            "location": {"building_storey": {"name": "Level 01"}},
            "field": None,
            "old_value": None,
            "new_value": {"name": "Beam 01"},
            "evidence": {"selector": "added/SYNTHETIC-BEAM-001"},
        },
        {
            "change_type": "deleted",
            "entity_type": "IfcColumn",
            "global_id": "SYNTHETIC-COLUMN-002",
            "location": {"building_storey": {"name": "Ground Floor"}},
            "field": None,
            "old_value": {"name": "Column 02"},
            "new_value": None,
            "evidence": {"selector": "deleted/SYNTHETIC-COLUMN-002"},
        },
        {
            "change_type": "property_modified",
            "entity_type": "IfcWall",
            "global_id": "SYNTHETIC-WALL-003",
            "location": {"building_storey": {"name": "Level 01"}},
            "field": {"property_set": "Pset_WallCommon", "name": "IsExternal"},
            "old_value": False,
            "new_value": True,
            "evidence": {"selector": "changed/SYNTHETIC-WALL-003"},
        },
    ]
    return {
        "source": {"file_name": "sample-baseline.ifc"},
        "revised": {"file_name": "sample-revised.ifc"},
        "summary": {
            "total_supported": 3,
            "added": 1,
            "deleted": 1,
            "property_modified": 1,
            "unsupported": 0,
        },
        "changes": changes,
    }


def save_state(window: MainWindow, path: Path) -> None:
    QApplication.processEvents()
    if not window.grab().save(str(path)):
        raise RuntimeError(f"Could not save {path.name}")


def save_settings(window: MainWindow, path: Path, tab_index: int = 0) -> None:
    dialog = AISettingsDialog(
        window.ai_settings, window, preferences=window.preferences
    )
    dialog.setStyleSheet(window.styleSheet())
    dialog.tabs.setCurrentIndex(tab_index)
    dialog.show()
    QApplication.processEvents()
    if not dialog.grab().save(str(path)):
        raise RuntimeError(f"Could not save {path.name}")
    dialog.close()


def main(output_dir: Path) -> None:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    for font_path in (
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path(r"C:\Windows\Fonts\msyh.ttc"),
    ):
        if font_path.is_file():
            QFontDatabase.addApplicationFont(str(font_path))
    window = MainWindow(
        report_root=output_dir / "reports",
        preferences=DesktopPreferences(language="zh_CN", theme="light"),
        persist_preferences=False,
    )
    window.resize(1120, 720)
    window.show()
    save_state(window, output_dir / "desktop-light-zh-home.png")
    window.ai_toggle.setChecked(True)
    QTest.qWait(220)
    save_state(window, output_dir / "desktop-light-zh-ai-on.png")
    window.ai_toggle.setChecked(False)
    QTest.qWait(220)
    save_settings(window, output_dir / "desktop-light-zh-settings.png")
    save_settings(window, output_dir / "desktop-light-zh-settings-ai.png", 1)
    window.report_page.load_report(
        synthetic_artifact(),
        output_dir / "synthetic-change-records.json",
        output_dir / "synthetic-report.html",
        explanation={
            "provider": "offline-sample",
            "model": "synthetic-model",
            "explanation": {
                "summary": "本次示例包含三项受支持的变化：新增、删除与属性修改各一项。",
                "key_changes": [
                    "新增一根 IfcBeam。",
                    "删除一根 IfcColumn。",
                    "一面 IfcWall 的 IsExternal 属性发生变化。",
                ],
                "rational_analysis": "建议先核对属性语义变化，再结合原始模型审阅新增与删除构件。",
                "limitations": [
                    "这是完全合成的界面示例，不代表真实项目结论。"
                ],
            },
        },
    )
    window.stack.setCurrentWidget(window.report_page)
    save_state(window, output_dir / "desktop-light-zh-report.png")
    window.report_page.review_tabs.setCurrentIndex(1)
    save_state(window, output_dir / "desktop-light-zh-ai-report.png")
    window.report_page.review_tabs.setCurrentIndex(0)
    window.resize(920, 640)
    save_state(window, output_dir / "desktop-light-zh-report-minimum.png")

    window.resize(1120, 720)
    window.preferences = DesktopPreferences(language="en", theme="dark")
    window.retranslate_ui()
    window.apply_theme()
    window.stack.setCurrentWidget(window.file_page)
    save_state(window, output_dir / "desktop-dark-en-home.png")
    save_settings(window, output_dir / "desktop-dark-en-settings.png")
    save_settings(window, output_dir / "desktop-dark-en-settings-ai.png", 1)
    window.stack.setCurrentWidget(window.report_page)
    save_state(window, output_dir / "desktop-dark-en-report.png")
    window.close()
    app.processEvents()
    for name in (
        "desktop-light-zh-home.png",
        "desktop-light-zh-ai-on.png",
        "desktop-light-zh-report.png",
        "desktop-light-zh-ai-report.png",
        "desktop-light-zh-report-minimum.png",
        "desktop-light-zh-settings.png",
        "desktop-light-zh-settings-ai.png",
        "desktop-dark-en-home.png",
        "desktop-dark-en-report.png",
        "desktop-dark-en-settings.png",
        "desktop-dark-en-settings-ai.png",
    ):
        print(output_dir / name)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: render_desktop_design_screens.py OUTPUT_DIR")
    main(Path(sys.argv[1]))
