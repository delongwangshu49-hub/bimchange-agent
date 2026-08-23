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
    BRAND_ANIMATION_PATH,
    DISPLAY_VERSION,
    BrandSplash,
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
        {
            "change_type": "geometry_modified",
            "entity_type": "IfcBeam",
            "global_id": "SYNTHETIC-BEAM-003",
            "location": {"building_storey": {"name": "Level 02"}},
            "field": None,
            "old_value": {"origin_m": [1.0, 2.0, 3.0]},
            "new_value": {"origin_m": [1.25, 2.0, 3.0]},
            "geometry_change": {
                "subtype": "placement_translation",
                "coordinate_frame": "project_world",
                "length_unit": "m",
                "old_origin": [1.0, 2.0, 3.0],
                "new_origin": [1.25, 2.0, 3.0],
                "delta": [0.25, 0.0, 0.0],
                "distance": 0.25,
                "local_shape_unchanged": True,
            },
            "evidence": {
                "selector": "changed.SYNTHETIC-BEAM-003.geometry_changed"
            },
        },
    ]
    return {
        "source": {"file_name": "previous.ifc"},
        "revised": {"file_name": "revised.ifc"},
        "summary": {
            "total_supported": 3,
            "added": 1,
            "deleted": 0,
            "property_modified": 1,
            "geometry_modified": 1,
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
            self.assertIn("combo-chevron-dark.xpm", window.styleSheet())
            self.assertLessEqual(window.width(), 1120)
            self.assertLessEqual(window.height(), 720)
            window.ai_toggle.setChecked(True)
            self.assertTrue(window.ai_settings.enabled)
            self.assertIn("bounded records sent", window.ai_toggle_label.text())
            QTest.qWait(220)
            self.assertAlmostEqual(window.ai_toggle.position, 1.0, places=2)
            self.assertFalse(window.windowIcon().isNull())
            self.assertEqual(DISPLAY_VERSION, "0.8.0-rc.1")
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
                explanation={
                    "provider": "offline-test",
                    "model": "synthetic-model",
                    "explanation": {
                        "summary": "Two supported changes were found.",
                        "key_changes": ["A beam was added."],
                        "rational_analysis": "Review the wall property change first.",
                        "limitations": ["Synthetic evidence only."],
                    },
                },
            )
            self.assertEqual(window.report_page.table.rowCount(), 3)
            self.assertEqual(
                window.report_page.card_labels["geometry_modified"].text(), "1"
            )
            self.assertEqual(
                window.report_page.table.verticalScrollMode(),
                QAbstractItemView.ScrollMode.ScrollPerPixel,
            )
            self.assertFalse(window.report_page.splitter.opaqueResize())
            window.stack.setCurrentWidget(window.report_page)
            window.resize(1000, 680)
            window.show()
            self.app.processEvents()
            self.assertEqual(
                window.report_page.splitter.orientation(), Qt.Orientation.Vertical
            )
            window.report_page.splitter.setSizes([1, 10_000])
            self.app.processEvents()
            vertical_sizes = window.report_page.splitter.sizes()
            self.assertGreaterEqual(vertical_sizes[0], 90)
            self.assertGreaterEqual(vertical_sizes[1], 90)
            window.resize(1400, 820)
            self.app.processEvents()
            self.assertEqual(
                window.report_page.splitter.orientation(), Qt.Orientation.Horizontal
            )
            window.report_page.splitter.setSizes([10_000, 1])
            self.app.processEvents()
            horizontal_sizes = window.report_page.splitter.sizes()
            self.assertGreaterEqual(horizontal_sizes[0], 520)
            self.assertGreaterEqual(horizontal_sizes[1], 340)
            self.assertIn(
                "Brief rational analysis",
                window.report_page.ai_output.toPlainText(),
            )
            self.assertNotIn('"summary"', window.report_page.ai_output.toPlainText())
            window.report_page.search_filter.setText("WALL-002")
            self.app.processEvents()
            self.assertEqual(window.report_page.table.rowCount(), 1)
            self.assertIn("SYNTHETIC-WALL-002", window.report_page.detail_body.toPlainText())
            window.report_page.search_filter.clear()
            index = window.report_page.type_filter.findData("added")
            window.report_page.type_filter.setCurrentIndex(index)
            self.app.processEvents()
            self.assertEqual(window.report_page.table.rowCount(), 1)
            self.assertIn("Showing 1 of 3 changes", window.report_page.result_count.text())
            geometry_index = window.report_page.type_filter.findData(
                "geometry_modified"
            )
            window.report_page.type_filter.setCurrentIndex(geometry_index)
            self.app.processEvents()
            self.assertEqual(window.report_page.table.rowCount(), 1)
            detail = window.report_page.detail_body.toPlainText()
            self.assertIn("Placement translation", detail)
            self.assertIn("0.25", detail)
            window.close()

    def test_brand_splash_uses_packaged_animation(self) -> None:
        self.assertTrue(BRAND_ANIMATION_PATH.is_file())
        splash = BrandSplash()
        self.assertTrue(splash.movie.isValid())
        self.assertLessEqual(splash.width(), 720)
        self.assertAlmostEqual(splash.width() / splash.height(), 1120 / 360, places=1)
        splash.movie.stop()
        splash.close()


if __name__ == "__main__":
    unittest.main()
