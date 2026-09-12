"""Explicit local native/frozen R4 verification; no network or saved preferences."""
from __future__ import annotations

import json
import hashlib
import sys
import time
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from .r4_webengine_candidate import R4SpatialContextPane


def main() -> int:
    index = sys.argv.index("--smoke-r4")
    source, revised, report, output = map(Path, sys.argv[index + 1:index + 5])
    if output.exists():
        raise FileExistsError("Choose a fresh smoke output directory")
    output.mkdir(parents=True)
    artifact = json.loads(report.read_text(encoding="utf-8"))
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    pane = R4SpatialContextPane()
    pane.resize(1160, 780)
    pane.set_language("zh_CN")
    pane.set_inputs(source, revised, artifact)
    pane.show()
    loaded, errors, beats, timings = [], [], [], []
    pane.scene_loaded.connect(lambda *args: loaded.append(args))
    pane.scene_failed.connect(errors.append)
    timer = QTimer()
    timer.setInterval(20)
    timer.timeout.connect(lambda: beats.append(time.perf_counter()))
    timer.start()

    def until(condition, timeout=30):
        deadline = time.monotonic() + timeout
        while not condition() and not errors and time.monotonic() < deadline:
            app.processEvents()
            QTest.qWait(5)
        if errors or not condition():
            raise AssertionError(f"Native scene failed: {errors}; {pane.status.text()}")

    def js(expression):
        values = []
        pane._view.page().runJavaScript(expression, values.append)
        until(lambda: bool(values), 5)
        return values[0]

    def select(change, tag):
        count = len(loaded)
        start_beat = len(beats)
        started = time.perf_counter()
        pane.show_change(change)
        returned = time.perf_counter() - started
        until(lambda: len(loaded) > count)
        elapsed = time.perf_counter() - started
        samples = [started] + beats[start_beat:] + [time.perf_counter()]
        proof = json.loads(js("JSON.stringify(window.__R4_PROOF_STATE__)"))
        assert proof["targetGlobalId"] == change["global_id"] and proof["targetCount"] == 1
        assert proof["changeId"] == change["change_id"]
        grid = json.loads(js("JSON.stringify(window.__R4_GRID_STATE__)"))
        assert grid["plane"] == "XY" and grid["background"] == "#000000"
        assert 0 < grid["lineSegments"] <= 162 and not grid["buildingAxes"]
        timings.append({"tag": tag, "call_seconds": returned, "render_seconds": elapsed,
                        "reference_grid": grid,
                        "heartbeat_max_gap_seconds": max(b - a for a, b in zip(samples, samples[1:])),
                        "worker_cache_hit": pane._result["cache_hit"], "proof": proof})

    result = {}
    try:
        for i, change in enumerate(artifact["changes"]):
            select(change, f"first-{i}")
            js("document.querySelector('#focus').click()")
            QTest.qWait(150)
            pane.grab().save(str(output / f"shape-{change['change_type']}.png"))
        original_view, original_process = pane._view, pane._process
        original_pid = pane._process.processId()
        for i, change in enumerate(artifact["changes"]):
            select(change, f"cached-{i}")
            assert pane._result["cache_hit"]
            assert pane._view is original_view and pane._process is original_process
            assert pane._process.processId() == original_pid
        count = len(loaded)
        for change in artifact["changes"][:3]:
            pane.show_change(change)
        until(lambda: len(loaded) > count)
        assert len(loaded) == count + 1
        assert loaded[-1][0] == artifact["changes"][2]["global_id"]
        QTest.qWait(500)
        before = js("window.__R4_RENDER_COUNT__")
        QTest.qWait(600)
        after = js("window.__R4_RENDER_COUNT__")
        assert after == before, (before, after)
        pane.clear_selection()
        QTest.qWait(100)
        assert not json.loads(js("JSON.stringify(window.__R4_PROOF_STATE__)"))["ready"]
        result = {"status": "PASS", "frozen": bool(getattr(sys, "frozen", False)),
                  "timings": timings, "latest_selection_only": True,
                  "runtime_reused": True, "idle_frames_600ms": after - before,
                  "heartbeat_max_gap_seconds": max(b - a for a, b in zip(beats, beats[1:])),
                  "heartbeat_samples": len(beats), "errors": errors}
    except Exception as error:
        result = {"status": "FAIL", "error": str(error), "timings": timings, "errors": errors}
    finally:
        root = pane._temporary_root
        pane.close()
        app.processEvents()
        result["session_removed"] = not root or not root.exists()
        if getattr(sys, "frozen", False):
            with Path(sys.executable).open("rb") as executable:
                result["executable_sha256"] = hashlib.file_digest(executable, "sha256").hexdigest()
        (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["status"] == "PASS" and result["session_removed"] else 1
