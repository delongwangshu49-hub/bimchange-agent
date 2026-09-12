"""Capture actual 1.0.0 UI with a fresh, exclusively synthetic public demo."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
from generate_public_demo import generate
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from bimchange_agent.desktop_app import DesktopPreferences, MainWindow


def main(output: Path, demo: Path) -> None:
    if output.exists():
        raise FileExistsError("Choose a fresh screenshot directory")
    source, revised, report = generate(demo)
    output.mkdir(parents=True)
    app = QApplication([])
    window = MainWindow(report_root=demo / "ui-reports",
                        preferences=DesktopPreferences(language="zh_CN", theme="light"),
                        persist_preferences=False)
    window.resize(1480, 920)
    window.show()

    def grab(name):
        QTest.qWait(250)
        if not window.grab().save(str(output / name)):
            raise RuntimeError(name)

    try:
        grab("desktop-light-zh-home.png")
        window.preferences = DesktopPreferences(language="en", theme="dark")
        window.retranslate_ui()
        window.apply_theme()
        grab("desktop-dark-en-home.png")
        window.preferences = DesktopPreferences(language="zh_CN", theme="dark")
        window.retranslate_ui()
        window.apply_theme()
        artifact = json.loads(report.read_text(encoding="utf-8"))
        page = window.report_page
        page.load_report(artifact, report, demo / "report.html", None, source, revised)
        window.stack.setCurrentWidget(page)
        page.review_tabs.setCurrentIndex(2)
        pane = page.spatial_context
        loaded, errors = [], []
        pane.scene_loaded.connect(lambda *args: loaded.append(args))
        pane.scene_failed.connect(errors.append)
        change = next(c for c in artifact["changes"] if c["change_type"] == "property_modified")
        row = artifact["changes"].index(change)
        page.table.selectRow(row)
        pane.show_change(change)
        deadline = time.monotonic() + 120
        while not loaded and not errors and time.monotonic() < deadline:
            app.processEvents()
            QTest.qWait(10)
        if errors or not loaded:
            raise AssertionError(errors or "Scene timeout")
        pane._view.page().runJavaScript("document.querySelector('#focus').click()")
        QTest.qWait(400)
        grab("desktop-dark-zh-spatial.png")
        window.preferences = DesktopPreferences(language="en", theme="dark")
        window.retranslate_ui()
        window.apply_theme()
        grab("desktop-dark-en-spatial.png")
    finally:
        window.close()
        app.processEvents()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("demo", type=Path)
    args = parser.parse_args()
    main(args.output.resolve(), args.demo.resolve())
