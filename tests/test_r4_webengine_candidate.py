"""Opt-in offscreen WebEngine smoke test for the R4 desktop candidate."""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

if os.environ.get("BIMCHANGE_RUN_WEBENGINE_NATIVE") != "1":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from bimchange_agent.r4_webengine_candidate import (
    WEBENGINE_AVAILABLE,
    R4SpatialContextPane,
)
from bimchange_agent.desktop_app import ReportPage
from research.r4_spatial_context.fixture import generate_pair, guid
from tests.test_r4_spatial_candidate import CHANGES


CHANGE = {
    "change_id": "r4-change-added-beam",
    "change_type": "added",
    "entity_type": "IfcBeam",
    "global_id": guid("added-beam"),
}


def _artifact() -> dict:
    change = {
        **CHANGE,
        "location": {
            "building_storey": {
                "global_id": guid("storey-ground"),
                "name": "Ground Floor",
            }
        },
        "field": None,
        "old_value": None,
        "new_value": {"status": "present"},
        "geometry_change": None,
        "relationship_change": None,
        "evidence": {"selector": {"section": "added", "global_id": CHANGE["global_id"]}},
    }
    return {
        "source": {"file_name": "source.ifc"},
        "revised": {"file_name": "revised.ifc"},
        "summary": {
            "total_supported": 1,
            "added": 1,
            "deleted": 0,
            "property_modified": 0,
            "geometry_modified": 0,
            "relationship_modified": 0,
            "unsupported": 0,
        },
        "changes": [change],
    }


@unittest.skipUnless(
    os.environ.get("BIMCHANGE_RUN_WEBENGINE_TEST") == "1" and WEBENGINE_AVAILABLE,
    "WebEngine smoke test is opt-in",
)
class R4WebEngineCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def test_latest_selection_same_guid_cache_idle_and_worker_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, revised = generate_pair(root / "inputs")
            first = CHANGES[2]
            second = dict(first, change_id="same-guid-another-record", change_type="relationship_modified")
            pane = R4SpatialContextPane()
            pane.resize(1000, 700)
            pane.set_inputs(source, revised, {"changes": [first, second, CHANGES[1]]})
            loaded, failed = QSignalSpy(pane.scene_loaded), QSignalSpy(pane.scene_failed)
            pane.show()

            def until(condition):
                deadline = time.monotonic() + 15
                while not condition() and time.monotonic() < deadline:
                    self.app.processEvents()
                    QTest.qWait(5)
                self.assertTrue(condition(), pane.status.text())

            def js(expression):
                result = []
                pane._view.page().runJavaScript(expression, result.append)
                until(lambda: bool(result))
                return result[0]

            try:
                pane.show_change(CHANGES[1])
                until(lambda: pane._busy)
                pane.show_change(first)
                pane.show_change(second)
                until(lambda: loaded.count() == 1)
                self.assertEqual(loaded.at(0)[0], second["global_id"])
                proof = json.loads(js("JSON.stringify(window.__R4_PROOF_STATE__)"))
                self.assertEqual(proof["changeId"], second["change_id"])
                grid = json.loads(js("JSON.stringify(window.__R4_GRID_STATE__)"))
                self.assertEqual(grid["background"], "#000000")
                self.assertEqual(grid["plane"], "XY")
                self.assertFalse(grid["buildingAxes"])
                self.assertGreaterEqual(grid["spacingM"], 1)
                self.assertLessEqual(grid["lineSegments"], 162)
                self.assertEqual(js("getComputedStyle(document.querySelector('.stage')).backgroundColor"), "rgb(0, 0, 0)")
                original_view, original_worker = pane._view, pane._process
                pane.show_change(first)
                until(lambda: loaded.count() == 2)
                self.assertIs(pane._view, original_view)
                self.assertIs(pane._process, original_worker)
                proof = json.loads(js("JSON.stringify(window.__R4_PROOF_STATE__)"))
                self.assertEqual(proof["changeId"], first["change_id"])
                pane.show_change(second)
                until(lambda: loaded.count() == 3)
                self.assertTrue(pane._result["cache_hit"])
                QTest.qWait(400)
                frames = js("window.__R4_RENDER_COUNT__")
                QTest.qWait(400)
                self.assertEqual(js("window.__R4_RENDER_COUNT__"), frames)
                self.assertEqual(failed.count(), 0)
                js("window.clearScene()")
                self.assertEqual(js("window.__R4_GRID_STATE__ === null"), True)
                original_worker.kill()
                until(lambda: failed.count() == 1)
                pane.show_change(first)
                until(lambda: loaded.count() == 4)
                self.assertIsNot(pane._process, original_worker)
                session = pane._temporary_root
                pane.set_inputs(None, None, {"changes": []})
                until(lambda: not session.exists())
                self.assertIsNone(pane.current_global_id)
                self.assertIsNone(pane._view)
            finally:
                pane.close()
                self.app.processEvents()

    def test_off_record_webengine_loads_local_target(self) -> None:
        with tempfile.TemporaryDirectory(prefix="r4-webengine-test-") as temporary:
            root = Path(temporary)
            source, revised = generate_pair(root / "inputs")
            pane = R4SpatialContextPane()
            pane.resize(1100, 700)
            pane.set_inputs(source, revised, {"changes": [CHANGE]})
            loaded = QSignalSpy(pane.scene_loaded)
            failed = QSignalSpy(pane.scene_failed)
            pane.show()
            pane.show_change(CHANGE)
            deadline = time.monotonic() + 15
            while loaded.count() == 0 and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.01)
            self.assertTrue(
                loaded.count() > 0,
                f"{pane.status.text()} blocked={pane.blocked_request_count} url={pane._view.url().toString() if pane._view else 'none'} requests={pane._server.request_paths if pane._server else []} responses={pane._server.response_codes if pane._server else []}",
            )
            self.assertEqual(failed.count(), 0)
            self.assertTrue(pane.profile_is_off_the_record)
            ready_deadline = time.monotonic() + 2
            while time.monotonic() < ready_deadline:
                self.app.processEvents()
                time.sleep(0.01)

            result: list[str] = []
            loop = QEventLoop()
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(loop.quit)
            pane._view.page().runJavaScript(
                "JSON.stringify({status:document.querySelector('#status').textContent,buttons:document.querySelectorAll('button[data-change-id]').length,pressed:document.querySelector('button[aria-pressed=\"true\"]')?.textContent})",
                lambda value: (result.append(value), loop.quit()),
            )
            timer.start(5_000)
            loop.exec()
            self.assertTrue(result, "Viewer JavaScript did not return a result")
            state = json.loads(result[0])
            self.assertEqual(state["buttons"], 1)
            self.assertIn("Added · 1 target + 2 bounded context", state["status"])
            self.assertIn(CHANGE["global_id"], state["pressed"])
            self.assertGreaterEqual(pane.blocked_request_count, 1)
            self.assertTrue(
                all(not url.startswith(pane._server.allowed_prefix) for url in pane.blocked_request_urls)
            )
            self.assertTrue(
                all(path.startswith(f"/{pane._server.token}/") for path in pane._server.request_paths)
            )
            pane.close()
            self.app.processEvents()

    def test_report_row_opens_the_same_global_id(self) -> None:
        with tempfile.TemporaryDirectory(prefix="r4-row-webengine-test-") as temporary:
            root = Path(temporary)
            source, revised = generate_pair(root / "inputs")
            page = ReportPage(language="en")
            page.resize(1200, 760)
            page.load_report(
                _artifact(),
                root / "artifact.json",
                root / "report.html",
                None,
                source_ifc=source,
                revised_ifc=revised,
            )
            loaded = QSignalSpy(page.spatial_context.scene_loaded)
            page.show()
            page.review_tabs.setCurrentIndex(2)
            deadline = time.monotonic() + 15
            while loaded.count() == 0 and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(0.01)
            self.assertGreater(loaded.count(), 0, page.spatial_context.status.text())
            self.assertEqual(page.spatial_context.current_global_id, CHANGE["global_id"])
            self.assertEqual(loaded.at(0)[0], CHANGE["global_id"])
            page.spatial_context.close()
            page.close()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
