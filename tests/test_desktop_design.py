"""Offline desktop design tests that never open IFC files or model APIs."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractItemView

from bimchange_agent.desktop_app import (
    AISettingsDialog,
    DISPLAY_VERSION,
    DesktopAISettings,
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
            "change_type": "property_modified",
            "entity_type": "IfcWall",
            "global_id": "SYNTHETIC-WALL-002",
            "location": {"building_storey": {"name": "Ground Floor"}},
            "field": {"property_set": "Pset_WallCommon", "name": "IsExternal"},
            "old_value": False,
            "new_value": True,
            "evidence": {"selector": "changed/SYNTHETIC-WALL-002"},
        },
    ]
    return {
        "source": {"file_name": "previous.ifc"},
        "revised": {"file_name": "revised.ifc"},
        "summary": {
            "total_supported": 2,
            "added": 1,
            "deleted": 0,
            "property_modified": 1,
            "unsupported": 0,
        },
        "changes": changes,
    }


class DesktopDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_language_theme_and_ai_toggle_apply_without_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(
                report_root=Path(directory),
                preferences=DesktopPreferences(language="zh_CN", theme="light"),
                persist_preferences=False,
            )
            self.assertEqual(window.file_page.title.text(), "比较两个 IFC 版本")
            window.preferences = DesktopPreferences(language="en", theme="dark")
            window.retranslate_ui()
            window.apply_theme()
            self.assertEqual(window.file_page.title.text(), "Compare two IFC versions")
            self.assertIn("#17191C", window.styleSheet())
            window.ai_toggle.setChecked(True)
            self.assertTrue(window.ai_settings.enabled)
            self.assertIn("bounded records sent", window.ai_toggle_label.text())
            QTest.qWait(220)
            self.assertAlmostEqual(window.ai_toggle.position, 1.0, places=2)
            self.assertFalse(window.windowIcon().isNull())
            self.assertEqual(DISPLAY_VERSION, "0.5.0")
            window.brand_mark.setBusy(True)
            self.assertTrue(window.brand_mark.busy)
            self.assertTrue(window.brand_mark.isAnimating())
            window.brand_mark.setBusy(False)
            QTest.qWait(240)
            self.assertAlmostEqual(window.brand_mark.motion, 0.0, places=2)
            window.close()

    def test_settings_center_returns_general_and_ai_preferences(self) -> None:
        dialog = AISettingsDialog(
            DesktopAISettings(),
            preferences=DesktopPreferences(language="en", theme="dark"),
        )
        self.assertEqual(dialog.tabs.count(), 2)
        self.assertEqual(dialog.preferences().language, "en")
        self.assertEqual(dialog.preferences().theme, "dark")
        self.assertTrue(dialog.base_url.isReadOnly())
        dialog.provider.setCurrentIndex(dialog.provider.findData("openai"))
        self.assertEqual(dialog.base_url.text(), "https://api.openai.com/v1")
        self.assertEqual(dialog.model.text(), "gpt-5.6-luna")
        dialog.close()

    def test_report_filters_and_detail_use_synthetic_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            window = MainWindow(
                report_root=root,
                preferences=DesktopPreferences(language="en", theme="light"),
                persist_preferences=False,
            )
            window.report_page.load_report(
                synthetic_artifact(),
                root / "change-records.json",
                root / "report.html",
                explanation=None,
            )
            self.assertEqual(window.report_page.table.rowCount(), 2)
            self.assertEqual(
                window.report_page.table.verticalScrollMode(),
                QAbstractItemView.ScrollMode.ScrollPerPixel,
            )
            self.assertFalse(window.report_page.splitter.opaqueResize())
            window.stack.setCurrentWidget(window.report_page)
            window.resize(1100, 700)
            window.show()
            self.app.processEvents()
            self.assertEqual(
                window.report_page.splitter.orientation(), Qt.Orientation.Vertical
            )
            window.resize(1400, 820)
            self.app.processEvents()
            self.assertEqual(
                window.report_page.splitter.orientation(), Qt.Orientation.Horizontal
            )
            window.report_page.search_filter.setText("WALL-002")
            self.app.processEvents()
            self.assertEqual(window.report_page.table.rowCount(), 1)
            self.assertIn("SYNTHETIC-WALL-002", window.report_page.detail_body.toPlainText())
            window.report_page.search_filter.clear()
            index = window.report_page.type_filter.findData("added")
            window.report_page.type_filter.setCurrentIndex(index)
            self.app.processEvents()
            self.assertEqual(window.report_page.table.rowCount(), 1)
            self.assertIn("Showing 1 of 2 changes", window.report_page.result_count.text())
            window.close()


if __name__ == "__main__":
    unittest.main()
