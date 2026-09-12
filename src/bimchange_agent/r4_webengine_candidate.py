"""Responsive, session-scoped Qt WebEngine pane for local IFC geometry."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from importlib.util import find_spec
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal, QProcess, QProcessEnvironment, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from shiboken6 import isValid

from .r4_loopback import LocalViewerServer
from .r4_spatial_candidate import VIEWER_RESOURCE_ROOT

WEBENGINE_AVAILABLE = find_spec("PySide6.QtWebEngineWidgets") is not None


class R4SpatialContextPane(QWidget):
    scene_loaded = Signal(str, str, int)
    scene_failed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.source_ifc = self.revised_ifc = self.artifact = None
        self.language = "en"
        self._server = self._temporary_root = self._profile = None
        self._interceptor = self._view = self._page = self._process = None
        self._current_global_id = self._current_change_key = None
        self._request_id = 0
        self._pending = self._result = None
        self._busy = self._shell_ready = self._polling = False
        self._sent_id = None
        self._read_buffer = b""
        self._retired_processes = []
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(90)
        self._debounce.timeout.connect(self._dispatch)
        self._poll = QTimer(self)
        self._poll.setInterval(40)
        self._poll.timeout.connect(self._check_viewer)
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.setInterval(120_000)
        self._timeout.timeout.connect(self._timed_out)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self._layout.addWidget(self.status)
        self.set_language("en")

    def _text(self, zh: str, en: str) -> str:
        return zh if self.language == "zh_CN" else en

    def set_language(self, language: str) -> None:
        self.language = language
        if self._view:
            self._view.page().runJavaScript(f"window.setLanguage?.({json.dumps(language)})")
        if self._current_global_id is None:
            self.status.setText(self._text("选择一条变更，查看构件原形与周围环境。",
                                          "Select a change to view its actual geometry and nearby elements."))

    def set_inputs(self, source_ifc: Path | None, revised_ifc: Path | None, artifact: dict) -> None:
        self._clear_runtime()
        self.source_ifc = source_ifc.expanduser().resolve() if source_ifc else None
        self.revised_ifc = revised_ifc.expanduser().resolve() if revised_ifc else None
        self.artifact = artifact
        self.set_language(self.language)

    @property
    def current_global_id(self):
        return self._current_global_id

    @property
    def blocked_request_count(self):
        return int(self._interceptor.blocked_requests) if self._interceptor else 0

    @property
    def blocked_request_urls(self):
        return list(self._interceptor.blocked_urls) if self._interceptor else []

    @property
    def profile_is_off_the_record(self):
        return bool(self._profile and self._profile.isOffTheRecord())

    def _clear_runtime(self) -> None:
        self._request_id += 1
        self._debounce.stop()
        self._poll.stop()
        self._timeout.stop()
        self._pending = self._result = None
        self._busy = self._shell_ready = self._polling = False
        self._sent_id = None
        self._read_buffer = b""
        if self._view is not None:
            self._view.stop()
            self._layout.removeWidget(self._view)
            self._view.hide()
            self._view.deleteLater()
            self._view = None
        if self._page is not None:
            # A profile must outlive all its pages.
            profile = self._profile
            self._page.destroyed.connect(lambda: profile.deleteLater())
            self._page.deleteLater()
            self._page = None
        self._profile = self._interceptor = None
        if self._server is not None:
            self._server.close()
            self._server = None
        process, root = self._process, self._temporary_root
        self._process = self._temporary_root = None
        if process is not None:
            if process.state() != QProcess.ProcessState.NotRunning:
                self._retired_processes.append(process)
                process.finished.connect(lambda *_: self._cleanup_retired(process, root))
                process.kill()
            else:
                process.deleteLater()
                if root:
                    shutil.rmtree(root, ignore_errors=True)
        elif root:
            shutil.rmtree(root, ignore_errors=True)
        self._current_global_id = self._current_change_key = None

    def _cleanup_retired(self, process, root) -> None:
        if root:
            shutil.rmtree(root, ignore_errors=True)
        if process in self._retired_processes:
            self._retired_processes.remove(process)
        process.deleteLater()

    def clear_selection(self) -> None:
        self._request_id += 1
        self._pending = self._result = None
        self._current_global_id = self._current_change_key = None
        self._debounce.stop()
        self._poll.stop()
        if not self._busy:
            self._timeout.stop()
        if self._view:
            self._view.page().runJavaScript("window.clearScene?.()")
        self.set_language(self.language)

    def show_change(self, change: dict) -> None:
        key = json.dumps(change, sort_keys=True)
        if key == self._current_change_key:
            return
        if not WEBENGINE_AVAILABLE:
            self._fail("viewer_dependency_unavailable")
            return
        if self.source_ifc is None or self.revised_ifc is None or self.artifact is None:
            self._fail("viewer_inputs_unavailable")
            return
        self._request_id += 1
        self._current_change_key = key
        self._current_global_id = change.get("global_id")
        self._pending = (self._request_id, change)
        self._result = None
        self._sent_id = None
        self.status.setText(self._text("正在准备构件三维，可继续选择其他记录…",
                                      "Preparing geometry; you can continue selecting other records…"))
        if self._view:
            self._view.page().runJavaScript("window.clearScene?.(true)")
        self._debounce.start()

    def _ensure_runtime(self) -> None:
        if self._view is not None:
            return
        from .r4_webengine_runtime import (
            QWebEngineProfile, QWebEngineSettings, QWebEngineView,
            RequestInterceptor, RestrictedPage,
        )
        self._temporary_root = Path(tempfile.mkdtemp(prefix="bimchange-r4-session-"))
        shutil.copytree(VIEWER_RESOURCE_ROOT, self._temporary_root / "viewer")
        self._server = LocalViewerServer(self._temporary_root)
        self._server.start()
        self._profile = QWebEngineProfile(self)
        self._interceptor = RequestInterceptor(self._server.allowed_prefix, self._profile)
        self._profile.setUrlRequestInterceptor(self._interceptor)
        self._page = RestrictedPage(self._profile, self._server.allowed_prefix, self)
        for attribute in (
            QWebEngineSettings.WebAttribute.LocalStorageEnabled,
            QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,
            QWebEngineSettings.WebAttribute.PluginsEnabled,
            QWebEngineSettings.WebAttribute.FullScreenSupportEnabled,
            QWebEngineSettings.WebAttribute.ScreenCaptureEnabled,
        ):
            self._page.settings().setAttribute(attribute, False)
        self._view = QWebEngineView(self)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._view.setPage(self._page)
        self._layout.addWidget(self._view, stretch=1)
        self._view.setUrl(QUrl(self._server.url("viewer/index.html") + f"?embedded=1&lang={self.language}"))
        process = QProcess(self)
        self._process = process
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONPATH", str(Path(__file__).resolve().parent.parent))
        environment.insert("PYTHONIOENCODING", "utf-8")
        process.setProcessEnvironment(environment)
        process.setProgram(sys.executable)
        process.setArguments(["--r4-scene-worker"] if getattr(sys, "frozen", False)
                             else ["-B", "-m", "bimchange_agent.r4_scene_worker"])
        process.started.connect(self._dispatch)
        process.readyReadStandardOutput.connect(lambda: self._read_worker(process))
        process.readyReadStandardError.connect(lambda: process.readAllStandardError())
        process.finished.connect(lambda *_: self._worker_stopped(process))
        process.errorOccurred.connect(lambda *_: self._worker_stopped(process))
        process.start()
        self._poll.start()

    def _dispatch(self) -> None:
        if not self._pending or self._busy:
            return
        try:
            self._ensure_runtime()
            if self._busy or not self._pending:
                return
            if self._process.state() != QProcess.ProcessState.Running:
                return
            request_id, change = self._pending
            self._pending = None
            payload = {"id": request_id, "change": change, "inputs": {
                "source": str(self.source_ifc), "revised": str(self.revised_ifc),
                "artifact": self.artifact, "root": str(self._temporary_root)}}
            self._busy = True
            self._process.write((json.dumps(payload) + "\n").encode("utf-8"))
            self._timeout.start()
            self._poll.start()
        except Exception:
            self._fail("viewer_start_failed")

    def _read_worker(self, process) -> None:
        if process is not self._process:
            return
        self._read_buffer += bytes(process.readAllStandardOutput())
        while b"\n" in self._read_buffer:
            line, self._read_buffer = self._read_buffer.split(b"\n", 1)
            try:
                reply = json.loads(line)
            except (ValueError, UnicodeError):
                self._fail("scene_build_failed")
                continue
            self._busy = False
            self._timeout.stop()
            if reply.get("id") == self._request_id:
                if reply.get("ok"):
                    self._result = reply
                    self._server.allow_directory(Path(reply["manifest"]).parent)
                    self._poll.start()
                    self._timeout.start()
                else:
                    self._fail(reply.get("error", "scene_build_failed"))
            if self._pending:
                self._debounce.start()

    def _check_viewer(self) -> None:
        if not self._view or self._polling or not self.isVisible():
            return
        self._polling = True
        view = self._view
        request_id = self._request_id

        def received(value):
            if view is not self._view:
                return
            self._polling = False
            if request_id != self._request_id:
                return
            try:
                state = json.loads(value or "{}")
            except ValueError:
                return
            self._shell_ready = state.get("shell", False)
            if self._shell_ready and self._result and self._sent_id != request_id:
                self._sent_id = request_id
                relative = Path(self._result["manifest"]).relative_to(self._temporary_root).as_posix()
                view.page().runJavaScript(
                    f"window.loadManifest({json.dumps(self._server.url(relative))}, {request_id})")
            proof = state.get("proof") or {}
            if self._result and proof.get("requestId") == request_id:
                if proof.get("error"):
                    self._fail("viewer_load_failed")
                elif proof.get("ready"):
                    result = self._result
                    self._poll.stop()
                    self._timeout.stop()
                    role = self._text("旧版" if result["role"] == "source" else "新版", result["role"])
                    self.status.setText(self._text(
                        f"{role}构件 · {result['context_count']} 个周围构件 · {result['target']}",
                        f"{role} element · {result['context_count']} nearby elements · {result['target']}"))
                    self.scene_loaded.emit(result["target"], result["role"], result["context_count"])

        view.page().runJavaScript(
            "JSON.stringify({shell:window.__R4_SHELL_READY__,proof:window.__R4_PROOF_STATE__})", received)

    def _worker_stopped(self, process) -> None:
        if process is self._process and isValid(self._poll):
            self._clear_runtime()
            self._fail("scene_worker_stopped")

    def _timed_out(self) -> None:
        self._clear_runtime()
        self._fail("scene_timeout")

    def _fail(self, reason: str) -> None:
        self._poll.stop()
        self._timeout.stop()
        self._current_global_id = self._current_change_key = None
        self._result = None
        if self._view:
            self._view.page().runJavaScript("window.clearScene?.()")
        messages = {
            "direct_storey_unavailable": ("该构件没有唯一的直接楼层，无法建立局部场景。",
                                         "This element has no unique direct storey; local context is unavailable."),
            "input_changed_since_analysis": ("模型文件已变化，请重新分析后查看三维。",
                                            "The input changed. Run the analysis again before opening 3D."),
            "viewer_inputs_unavailable": ("请先选择 IFC 文件并完成分析。",
                                         "Select IFC files and run an analysis first."),
        }
        zh, en = messages.get(reason, ("暂时无法显示三维，请重新选择记录或重新分析。",
                                       "3D is unavailable. Select the record again or rerun the analysis."))
        self.status.setText(self._text(zh, en) + f" ({reason})")
        self.scene_failed.emit(reason)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._clear_runtime()
        for process in list(self._retired_processes):
            process.waitForFinished(1500)
        super().closeEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802
        if not self._busy:
            self._timeout.stop()
        if self._view:
            self._view.page().runJavaScript("window.setActive?.(false)")
        super().hideEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        if self._result and self._poll.isActive():
            self._timeout.start()
        if self._view:
            self._view.page().runJavaScript("window.setActive?.(true)")
        super().showEvent(event)
