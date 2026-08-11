"""Offscreen desktop smoke test; no model or external application is invoked."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import ifcopenshell

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from bimchange_agent.desktop_app import AISettingsDialog, DesktopAISettings, MainWindow


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPOSITORY_ROOT / "data" / "raw" / "Building-Structural.ifc"
REVISED = REPOSITORY_ROOT / "data" / "generated" / "Building-Structural-gate2-v2.ifc"


class DesktopSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_home_to_report_flow_without_ai(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(report_root=Path(directory))
            self.assertEqual(window.stack.currentIndex(), 0)
            self.assertFalse(window.ai_settings.enabled)
            window.file_page.source_zone.set_file(SOURCE)
            window.file_page.revised_zone.set_file(REVISED)
            self.assertTrue(window.file_page.start_button.isEnabled())
            window.start_analysis()
            deadline = time.monotonic() + 10
            while window.stack.currentIndex() != 1 and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.01)
            self.assertEqual(window.stack.currentIndex(), 1)
            self.assertEqual(window.report_page.card_labels["total_supported"].text(), "3")
            self.assertEqual(window.report_page.table.rowCount(), 3)
            self.assertIsNotNone(window.report_page.html_path)
            self.assertTrue(window.report_page.html_path.is_file())
            while window.thread is not None and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.01)
            window.close()

    def test_same_file_and_worker_failures_show_dialogs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(report_root=Path(directory))
            window.file_page.source_zone.set_file(SOURCE)
            window.file_page.revised_zone.set_file(SOURCE)
            with patch.object(QMessageBox, "warning", return_value=None) as warning:
                window.start_analysis()
            warning.assert_called_once()
            self.assertIsNone(window.thread)

            with patch.object(QMessageBox, "critical", return_value=None) as critical:
                window._analysis_failed("测试错误")
            critical.assert_called_once_with(window, "分析失败", "测试错误")
            self.assertTrue(window.settings_button.isEnabled())
            window.close()

    def test_disabling_ai_clears_key_and_official_endpoint_is_locked(self) -> None:
        dialog = AISettingsDialog(
            DesktopAISettings(enabled=True, api_key="do-not-persist")
        )
        self.assertTrue(dialog.base_url.isReadOnly())
        dialog.enabled.setChecked(False)
        self.assertEqual(dialog.settings().api_key, "")
        dialog.close()

    def test_invalid_selection_and_export_failure_show_dialogs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            window = MainWindow(report_root=Path(directory))
            missing = Path(directory) / "missing.ifc"
            with (
                patch(
                    "bimchange_agent.desktop_app.QFileDialog.getOpenFileName",
                    return_value=(str(missing), "IFC Files (*.ifc)"),
                ),
                patch.object(QMessageBox, "warning", return_value=None) as warning,
            ):
                window.file_page.source_zone.choose_file()
            warning.assert_called_once()

            window.report_page.artifact_path = Path(directory) / "report.json"
            window.report_page.artifact_path.write_text("{}", encoding="utf-8")
            target = Path(directory) / "exported.json"
            with (
                patch(
                    "bimchange_agent.desktop_app.QFileDialog.getSaveFileName",
                    return_value=(str(target), "JSON Files (*.json)"),
                ),
                patch(
                    "bimchange_agent.desktop_app.shutil.copy2",
                    side_effect=PermissionError("denied"),
                ),
                patch.object(QMessageBox, "critical", return_value=None) as critical,
            ):
                window.report_page._export_json()
            critical.assert_called_once()
            window.close()

    def test_unsupported_ifc_reaches_background_error_dialog_and_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            unsupported = root / "unsupported-ifc2x3.ifc"
            ifcopenshell.file(schema="IFC2X3").write(str(unsupported))
            window = MainWindow(report_root=root / "reports")
            window.file_page.source_zone.set_file(unsupported)
            window.file_page.revised_zone.set_file(REVISED)
            with patch.object(QMessageBox, "critical", return_value=None) as critical:
                window.start_analysis()
                deadline = time.monotonic() + 10
                while not critical.called and time.monotonic() < deadline:
                    self.app.processEvents()
                    time.sleep(0.01)
                self.assertTrue(critical.called)
                while window.thread is not None and time.monotonic() < deadline:
                    self.app.processEvents()
                    time.sleep(0.01)
            self.assertIsNone(window.thread)
            self.assertTrue(window.file_page.start_button.isEnabled())
            self.assertTrue(window.settings_button.isEnabled())
            window.close()


if __name__ == "__main__":
    unittest.main()
