"""Render deterministic offscreen desktop screenshots for visual QA."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from bimchange_agent.desktop_app import (  # noqa: E402
    DesktopPreferences,
    MainWindow,
)
from bimchange_agent.product_core import (  # noqa: E402
    CHANGE_RECORD_FILE_NAME,
    diff_ifc_pair,
    load_json,
)
from bimchange_agent.reporting import write_html_report  # noqa: E402


def main(output_dir: Path) -> None:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    window = MainWindow(
        report_root=output_dir / "reports",
        preferences=DesktopPreferences(language="zh_CN", theme="light"),
        persist_preferences=False,
    )
    window.resize(1240, 820)
    window.show()
    app.processEvents()
    if not window.grab().save(str(output_dir / "desktop-home.png")):
        raise RuntimeError("Could not save home screenshot")

    source = REPOSITORY_ROOT / "data" / "raw" / "Building-Structural.ifc"
    revised = (
        REPOSITORY_ROOT
        / "data"
        / "generated"
        / "Building-Structural-gate2-v2.ifc"
    )
    with tempfile.TemporaryDirectory() as directory:
        report_dir = Path(directory)
        result = diff_ifc_pair(source, revised, report_dir)
        artifact_path = Path(result["change_records"])
        artifact = load_json(artifact_path)
        html_path = write_html_report(artifact, report_dir / "report.html")
        window.report_page.load_report(
            artifact, artifact_path, html_path, explanation=None
        )
        window.stack.setCurrentWidget(window.report_page)
        app.processEvents()
        if not window.grab().save(str(output_dir / "desktop-report.png")):
            raise RuntimeError("Could not save report screenshot")
    window.close()
    print(output_dir / "desktop-home.png")
    print(output_dir / "desktop-report.png")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: render_desktop_screens.py OUTPUT_DIR")
    main(Path(sys.argv[1]))
