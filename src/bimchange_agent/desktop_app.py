"""PySide6 desktop shell for the bounded Windows product preview."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QStandardPaths, Qt, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QCloseEvent, QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .ai_providers import (
    DeepSeekExplanationProvider,
    ProviderConfigurationError,
    ProviderSettings,
    provider_catalog,
)
from .product_core import (
    CHANGE_RECORD_FILE_NAME,
    ProductBoundaryError,
    diff_ifc_pair,
    load_json,
)
from .reporting import write_html_report


APP_NAME = "BIMChange-Agent"
DISPLAY_VERSION = "0.2.0 Preview 1"
HTML_REPORT_FILE_NAME = "report.html"


def _friendly_error_message(error: Exception) -> str:
    if isinstance(error, ProductBoundaryError):
        return str(error)
    if isinstance(error, OSError):
        return (
            "无法读取输入文件或写入本地报告目录。请检查文件权限、磁盘空间，"
            "并确认文件未被其他程序锁定。"
        )
    if isinstance(error, (json.JSONDecodeError, TypeError, ValueError)):
        return f"输入或分析产物格式无效：{error}"
    return (
        f"发生未预期错误（{error.__class__.__name__}）。请重试；若问题持续，"
        "请在 GitHub Issues 反馈输入文件的格式、大小和复现步骤，勿上传敏感模型。"
    )


@dataclass
class DesktopAISettings:
    enabled: bool = False
    provider_id: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    api_key: str = ""


class FileDropZone(QFrame):
    """Clickable and droppable IFC path selector."""

    path_changed = Signal(object)

    def __init__(self, title: str, subtitle: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path: Path | None = None
        self.setAcceptDrops(True)
        self.setObjectName("dropZone")
        self.setMinimumHeight(230)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        layout.addStretch()
        self.title_label = QLabel(title)
        self.title_label.setObjectName("dropTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        self.detail_label = QLabel(subtitle)
        self.detail_label.setWordWrap(True)
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_label.setObjectName("dropDetail")
        layout.addWidget(self.detail_label)
        self.select_button = QPushButton("选择 IFC 文件")
        self.select_button.setObjectName("secondaryButton")
        self.select_button.clicked.connect(self.choose_file)
        layout.addWidget(self.select_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

    @property
    def path(self) -> Path | None:
        return self._path

    @staticmethod
    def accepts_path(path: Path) -> bool:
        return path.is_file() and path.suffix.lower() == ".ifc"

    def set_file(self, path: Path) -> None:
        path = path.expanduser().resolve()
        if not self.accepts_path(path):
            raise ValueError("请选择有效的 .ifc 文件")
        self._path = path
        size_mib = path.stat().st_size / 1024 / 1024
        self.detail_label.setText(f"{path.name}\n{size_mib:.2f} MiB")
        self.setProperty("hasFile", True)
        self.style().unpolish(self)
        self.style().polish(self)
        self.path_changed.emit(path)

    @Slot()
    def choose_file(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self, "选择 IFC 文件", "", "IFC Files (*.ifc)"
        )
        if selected:
            try:
                self.set_file(Path(selected))
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, "文件选择失败", _friendly_error_message(error))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            path = Path(urls[0].toLocalFile())
            if self.accepts_path(path):
                event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            try:
                self.set_file(Path(urls[0].toLocalFile()))
                event.acceptProposedAction()
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, "拖拽文件失败", _friendly_error_message(error))


class AISettingsDialog(QDialog):
    """Session-only provider settings; the secret is never persisted."""

    def __init__(
        self, settings: DesktopAISettings, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI 设置")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        self.enabled = QCheckBox("启用 AI 解读（默认关闭）")
        self.enabled.setChecked(settings.enabled)
        layout.addWidget(self.enabled)
        form = QFormLayout()
        self.provider = QComboBox()
        for descriptor in provider_catalog():
            suffix = "" if descriptor.status == "enabled" else " · 后续版本支持"
            self.provider.addItem(descriptor.display_name + suffix, descriptor.provider_id)
            if descriptor.status != "enabled":
                item = self.provider.model().item(self.provider.count() - 1)
                if item is not None:
                    item.setEnabled(False)
        current_index = self.provider.findData(settings.provider_id)
        self.provider.setCurrentIndex(max(0, current_index))
        form.addRow("服务商", self.provider)
        self.base_url = QLineEdit(settings.base_url)
        self.base_url.setReadOnly(True)
        self.base_url.setToolTip("Preview 1 仅连接 DeepSeek 官方 API 地址")
        form.addRow("API Base URL", self.base_url)
        self.model = QLineEdit(settings.model)
        form.addRow("模型", self.model)
        self.api_key = QLineEdit(settings.api_key)
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("仅保存在本次运行内存中")
        form.addRow("API Key", self.api_key)
        layout.addLayout(form)
        note = QLabel(
            "关闭软件后 API Key 会被清除。确定性差分始终在本地执行，"
            "AI 只接收最多 200 条规范化 Change Records，不发送 IFC 文件或本地文件名；"
            "记录仍可能包含构件名称、楼层和属性值，请仅在确认项目允许时开启。"
        )
        note.setWordWrap(True)
        note.setObjectName("muted")
        layout.addWidget(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def settings(self) -> DesktopAISettings:
        enabled = self.enabled.isChecked()
        return DesktopAISettings(
            enabled=enabled,
            provider_id=str(self.provider.currentData()),
            base_url=self.base_url.text().strip(),
            model=self.model.text().strip(),
            api_key=self.api_key.text() if enabled else "",
        )

    def accept(self) -> None:
        candidate = self.settings()
        if candidate.enabled:
            if not candidate.model or not candidate.api_key.strip():
                QMessageBox.warning(self, "设置无效", "启用 AI 时必须填写模型和 API Key。")
                return
            try:
                DeepSeekExplanationProvider(
                    ProviderSettings(
                        provider_id=candidate.provider_id,
                        base_url=candidate.base_url,
                        model=candidate.model,
                    )
                )
            except ProviderConfigurationError as error:
                QMessageBox.warning(self, "设置无效", str(error))
                return
        super().accept()


class FileSelectionPage(QWidget):
    start_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 32, 48, 40)
        layout.setSpacing(20)
        title = QLabel("比较两个 IFC 版本")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        subtitle = QLabel("选择或拖入旧版本与新版本 IFC 文件，随后生成可追溯的变更报告。")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        preview_note = QLabel("早期工程预览 · 用于验证工作流，不代表最终产品效果")
        preview_note.setObjectName("previewNote")
        preview_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(preview_note)
        zones = QHBoxLayout()
        zones.setSpacing(18)
        self.source_zone = FileDropZone("旧版本 IFC", "点击选择，或将 .ifc 文件拖到此处")
        self.revised_zone = FileDropZone("新版本 IFC", "点击选择，或将 .ifc 文件拖到此处")
        zones.addWidget(self.source_zone)
        zones.addWidget(self.revised_zone)
        layout.addLayout(zones)
        self.boundary = QLabel("首版边界：IFC4 · 单文件 ≤ 50 MiB · 每版 ≤ 5,000 个构件")
        self.boundary.setObjectName("muted")
        self.boundary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.boundary)
        self.start_button = QPushButton("开始分析")
        self.start_button.setObjectName("primaryButton")
        self.start_button.setMinimumHeight(46)
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_requested)
        layout.addWidget(self.start_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.source_zone.path_changed.connect(self._update_ready)
        self.revised_zone.path_changed.connect(self._update_ready)

    @Slot()
    def _update_ready(self) -> None:
        self.start_button.setEnabled(
            self.source_zone.path is not None and self.revised_zone.path is not None
        )

    def set_busy(self, busy: bool) -> None:
        self.source_zone.setEnabled(not busy)
        self.revised_zone.setEnabled(not busy)
        self.start_button.setEnabled(
            not busy
            and self.source_zone.path is not None
            and self.revised_zone.path is not None
        )


class ReportPage(QWidget):
    new_analysis_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.artifact_path: Path | None = None
        self.html_path: Path | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 28)
        top = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("分析报告")
        title.setObjectName("pageTitle")
        heading.addWidget(title)
        self.file_pair = QLabel()
        self.file_pair.setObjectName("pageSubtitle")
        heading.addWidget(self.file_pair)
        top.addLayout(heading)
        top.addStretch()
        self.new_button = QPushButton("重新分析")
        self.new_button.clicked.connect(self.new_analysis_requested)
        top.addWidget(self.new_button)
        layout.addLayout(top)

        cards = QGridLayout()
        self.card_labels: dict[str, QLabel] = {}
        card_specs = (
            ("total_supported", "受支持变更"),
            ("added", "新增"),
            ("deleted", "删除"),
            ("property_modified", "属性修改"),
            ("unsupported", "未支持"),
        )
        for column, (key, label) in enumerate(card_specs):
            frame = QFrame()
            frame.setObjectName("summaryCard")
            frame_layout = QVBoxLayout(frame)
            caption = QLabel(label)
            caption.setObjectName("muted")
            value = QLabel("0")
            value.setObjectName("summaryValue")
            frame_layout.addWidget(caption)
            frame_layout.addWidget(value)
            cards.addWidget(frame, 0, column)
            self.card_labels[key] = value
        layout.addLayout(cards)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["类型", "实体", "GlobalId", "楼层", "字段", "旧值", "新值"]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, stretch=3)

        ai_title = QLabel("AI 解读")
        ai_title.setObjectName("sectionTitle")
        layout.addWidget(ai_title)
        self.ai_output = QTextBrowser()
        self.ai_output.setMinimumHeight(110)
        layout.addWidget(self.ai_output, stretch=1)

        actions = QHBoxLayout()
        self.export_json = QPushButton("导出 JSON")
        self.export_html = QPushButton("导出 HTML")
        self.open_folder = QPushButton("打开报告文件夹")
        self.export_json.clicked.connect(self._export_json)
        self.export_html.clicked.connect(self._export_html)
        self.open_folder.clicked.connect(self._open_folder)
        actions.addWidget(self.export_json)
        actions.addWidget(self.export_html)
        actions.addWidget(self.open_folder)
        actions.addStretch()
        layout.addLayout(actions)

    def load_report(
        self,
        artifact: dict[str, Any],
        artifact_path: Path,
        html_path: Path,
        explanation: dict[str, Any] | None,
    ) -> None:
        self.artifact_path = artifact_path
        self.html_path = html_path
        self.file_pair.setText(
            f"{artifact['source']['file_name']}  →  {artifact['revised']['file_name']}"
        )
        for key, label in self.card_labels.items():
            label.setText(str(artifact["summary"][key]))
        self.table.setRowCount(len(artifact["changes"]))
        for row, change in enumerate(artifact["changes"]):
            storey = change["location"]["building_storey"]
            field = change["field"]
            values = (
                change["change_type"],
                change["entity_type"],
                change["global_id"],
                storey["name"] if storey else "—",
                f"{field['property_set']}.{field['name']}" if field else "—",
                self._display_value(change["old_value"]),
                self._display_value(change["new_value"]),
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
        if explanation is None:
            self.ai_output.setPlainText("本次分析未启用 AI。确定性差分报告仍然完整可用。")
        else:
            content = explanation.get("explanation", explanation)
            self.ai_output.setPlainText(
                json.dumps(content, indent=2, ensure_ascii=False)
            )

    @staticmethod
    def _display_value(value: Any) -> str:
        if value is None:
            return "—"
        if isinstance(value, (dict, list, bool, int, float)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value)

    def _copy_report(self, source: Path | None, title: str, pattern: str) -> None:
        if source is None:
            QMessageBox.warning(self, "无法导出", "当前没有可导出的报告文件。")
            return
        target, _ = QFileDialog.getSaveFileName(self, title, source.name, pattern)
        if target:
            try:
                target_path = Path(target).expanduser().resolve()
                if source.resolve() == target_path:
                    QMessageBox.information(self, "无需导出", "目标位置就是当前报告文件。")
                    return
                temporary = target_path.with_name(
                    f".{target_path.name}.{uuid.uuid4().hex}.tmp"
                )
                try:
                    shutil.copy2(source, temporary)
                    temporary.replace(target_path)
                finally:
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError:
                        pass
            except OSError as error:
                QMessageBox.critical(self, "导出失败", _friendly_error_message(error))

    @Slot()
    def _export_json(self) -> None:
        self._copy_report(self.artifact_path, "导出 JSON", "JSON Files (*.json)")

    @Slot()
    def _export_html(self) -> None:
        self._copy_report(self.html_path, "导出 HTML", "HTML Files (*.html)")

    @Slot()
    def _open_folder(self) -> None:
        if self.artifact_path is not None:
            opened = QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self.artifact_path.parent))
            )
            if not opened:
                QMessageBox.warning(
                    self, "无法打开文件夹", "系统未能打开本次报告目录。"
                )
        else:
            QMessageBox.warning(self, "无法打开文件夹", "当前还没有生成报告。")


class AnalysisWorker(QObject):
    progress = Signal(str)
    finished = Signal(object, object, object, object)
    failed = Signal(str)

    def __init__(
        self,
        source: Path,
        revised: Path,
        output_dir: Path,
        ai_settings: DesktopAISettings,
    ) -> None:
        super().__init__()
        self.source = source
        self.revised = revised
        self.output_dir = output_dir
        self.ai_settings = ai_settings

    @Slot()
    def run(self) -> None:
        try:
            self.progress.emit("正在检查并比较 IFC 文件…")
            result = diff_ifc_pair(self.source, self.revised, self.output_dir)
            artifact_path = Path(result["change_records"])
            artifact = load_json(artifact_path)
            explanation = None
            if self.ai_settings.enabled:
                self.progress.emit("确定性差分完成，正在请求 DeepSeek 解读…")
                try:
                    provider = DeepSeekExplanationProvider(
                        ProviderSettings(
                            provider_id=self.ai_settings.provider_id,
                            base_url=self.ai_settings.base_url,
                            model=self.ai_settings.model,
                        )
                    )
                    explanation = provider.explain(
                        artifact, api_key=self.ai_settings.api_key
                    )
                except Exception:
                    explanation = {
                        "provider": "deepseek",
                        "model": self.ai_settings.model,
                        "status": "ERROR",
                        "explanation": {
                            "summary": "AI 解读未生成；确定性差分报告仍然有效。",
                            "key_changes": [],
                            "limitations": ["DeepSeek 请求或响应处理失败，请检查设置后重试。"],
                        },
                    }
            self.progress.emit("正在生成 HTML 报告…")
            html_path = write_html_report(
                artifact,
                self.output_dir / HTML_REPORT_FILE_NAME,
                explanation=explanation,
            )
            self.finished.emit(artifact, artifact_path, html_path, explanation)
        except Exception as error:
            self.failed.emit(_friendly_error_message(error))


class MainWindow(QMainWindow):
    def __init__(self, report_root: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — {DISPLAY_VERSION}")
        self.resize(1240, 820)
        self.setMinimumSize(980, 680)
        self.ai_settings = DesktopAISettings()
        self.report_root = report_root or self._default_report_root()
        self.thread: QThread | None = None
        self.worker: AnalysisWorker | None = None

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QFrame()
        header.setObjectName("appHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(28, 16, 28, 16)
        brand = QLabel(f"{APP_NAME} · {DISPLAY_VERSION}")
        brand.setObjectName("brand")
        header_layout.addWidget(brand)
        header_layout.addStretch()
        self.ai_status = QLabel("AI：关闭")
        self.ai_status.setObjectName("muted")
        header_layout.addWidget(self.ai_status)
        self.settings_button = QPushButton("AI 设置")
        self.settings_button.clicked.connect(self.open_ai_settings)
        header_layout.addWidget(self.settings_button)
        outer.addWidget(header)

        self.stack = QStackedWidget()
        self.file_page = FileSelectionPage()
        self.report_page = ReportPage()
        self.stack.addWidget(self.file_page)
        self.stack.addWidget(self.report_page)
        outer.addWidget(self.stack, stretch=1)

        self.progress_panel = QFrame()
        self.progress_panel.setObjectName("progressPanel")
        progress_layout = QHBoxLayout(self.progress_panel)
        self.progress_label = QLabel("正在分析…")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setMaximumWidth(260)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addStretch()
        progress_layout.addWidget(self.progress_bar)
        self.progress_panel.hide()
        outer.addWidget(self.progress_panel)
        self.setCentralWidget(central)

        self.file_page.start_requested.connect(self.start_analysis)
        self.report_page.new_analysis_requested.connect(self.show_file_page)
        self.setStyleSheet(APP_STYLESHEET)

    @staticmethod
    def _default_report_root() -> Path:
        local_data = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation
        )
        base = (
            Path(local_data)
            if local_data
            else Path(tempfile.gettempdir()) / APP_NAME
        )
        return base / "Reports"

    @Slot()
    def open_ai_settings(self) -> None:
        dialog = AISettingsDialog(self.ai_settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.ai_settings = dialog.settings()
            self.ai_status.setText(
                f"AI：DeepSeek · {self.ai_settings.model}"
                if self.ai_settings.enabled
                else "AI：关闭"
            )

    def _new_run_dir(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return self.report_root / f"report-{stamp}-{uuid.uuid4().hex[:8]}"

    @Slot()
    def start_analysis(self) -> None:
        if self.thread is not None and self.thread.isRunning():
            QMessageBox.information(self, "分析进行中", "请等待当前分析完成。")
            return
        source = self.file_page.source_zone.path
        revised = self.file_page.revised_zone.path
        if source is None or revised is None:
            QMessageBox.warning(self, "缺少文件", "请先选择旧版和新版 IFC 文件。")
            return
        if source.resolve() == revised.resolve():
            QMessageBox.warning(
                self,
                "文件相同",
                "旧版和新版选择了同一个文件。请分别选择两个 IFC 版本。",
            )
            return
        if self.ai_settings.enabled and not self.ai_settings.api_key.strip():
            QMessageBox.warning(self, "缺少 API Key", "请先在 AI 设置中填写 DeepSeek API Key。")
            return
        self.file_page.set_busy(True)
        self.settings_button.setEnabled(False)
        self.progress_panel.show()
        output_dir = self._new_run_dir()
        self.thread = QThread(self)
        self.worker = AnalysisWorker(
            source, revised, output_dir, DesktopAISettings(**vars(self.ai_settings))
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.progress_label.setText)
        self.worker.finished.connect(self._analysis_finished)
        self.worker.failed.connect(self._analysis_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._thread_finished)
        self.thread.start()

    @Slot(object, object, object, object)
    def _analysis_finished(
        self,
        artifact: dict[str, Any],
        artifact_path: Path,
        html_path: Path,
        explanation: dict[str, Any] | None,
    ) -> None:
        self.report_page.load_report(
            artifact, artifact_path, html_path, explanation
        )
        self.stack.setCurrentWidget(self.report_page)
        self.progress_panel.hide()
        if explanation is not None and explanation.get("status") == "ERROR":
            QMessageBox.warning(
                self,
                "AI 解读失败",
                "本地确定性差分与报告已经完成，但 DeepSeek 解读未生成。"
                "请检查网络和 AI 设置后重新分析。",
            )

    @Slot(str)
    def _analysis_failed(self, message: str) -> None:
        self.progress_panel.hide()
        self.file_page.set_busy(False)
        self.settings_button.setEnabled(True)
        QMessageBox.critical(self, "分析失败", message)

    @Slot()
    def _thread_finished(self) -> None:
        self.file_page.set_busy(False)
        self.settings_button.setEnabled(True)
        self.thread = None
        self.worker = None

    @Slot()
    def show_file_page(self) -> None:
        self.stack.setCurrentWidget(self.file_page)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.thread is not None and self.thread.isRunning():
            QMessageBox.information(self, "分析进行中", "请等待当前分析完成后再关闭软件。")
            event.ignore()
            return
        super().closeEvent(event)


APP_STYLESHEET = """
QWidget { background: #f3f6f7; color: #1a242d; font-family: "Segoe UI", "Microsoft YaHei"; font-size: 14px; }
#appHeader { background: #ffffff; border-bottom: 1px solid #dce3e7; }
#brand { font-size: 20px; font-weight: 700; color: #244c5d; }
#pageTitle { font-size: 28px; font-weight: 700; color: #17242d; }
#pageSubtitle, #muted { color: #687681; }
#previewNote { color: #765d32; background: #f5ecd9; border: 1px solid #e2d0aa; border-radius: 8px; padding: 7px 12px; }
#dropZone { background: #ffffff; border: 2px dashed #b8c6cd; border-radius: 14px; }
#dropZone[hasFile="true"] { border-color: #3f778a; background: #f2f8fa; }
#dropTitle { font-size: 19px; font-weight: 650; }
#dropDetail { color: #667782; }
QPushButton { background: #ffffff; border: 1px solid #bdc9cf; border-radius: 8px; padding: 8px 15px; }
QPushButton:hover { border-color: #567f90; background: #f7fafb; }
QPushButton:disabled { color: #9aa5ab; background: #edf0f1; }
#primaryButton { min-width: 190px; color: white; background: #315f72; border-color: #315f72; font-weight: 650; }
#primaryButton:hover { background: #284f60; }
#secondaryButton { min-width: 140px; }
#summaryCard { background: #ffffff; border: 1px solid #dce3e7; border-radius: 10px; }
#summaryValue { color: #315f72; font-size: 24px; font-weight: 700; }
#sectionTitle { font-size: 17px; font-weight: 650; margin-top: 4px; }
#progressPanel { background: #e8f0f3; border-top: 1px solid #cad8dd; }
QTableWidget, QTextBrowser, QLineEdit, QComboBox { background: #ffffff; border: 1px solid #d5dde1; border-radius: 7px; }
QHeaderView::section { background: #e9eef1; border: none; border-bottom: 1px solid #ccd6db; padding: 8px; font-weight: 650; }
"""


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("BIMChange-Agent")
    if "--smoke-diff" in sys.argv:
        argument_index = sys.argv.index("--smoke-diff")
        arguments = sys.argv[argument_index + 1 : argument_index + 4]
        if len(arguments) != 3:
            return 2
        try:
            diff_ifc_pair(Path(arguments[0]), Path(arguments[1]), Path(arguments[2]))
        except Exception:
            return 2
        return 0
    if "--smoke-test" in sys.argv:
        smoke_root = Path(tempfile.gettempdir()) / "bimchange-agent-desktop-smoke"
        window = MainWindow(report_root=smoke_root)
        window.show()
        app.processEvents()
        window.close()
        return 0

    window = MainWindow()
    def show_unhandled_error(
        error_type: type[BaseException], error: BaseException, _traceback: object
    ) -> None:
        message = _friendly_error_message(
            error if isinstance(error, Exception) else RuntimeError(str(error_type))
        )
        QMessageBox.critical(window, "软件发生错误", message)

    sys.excepthook = show_unhandled_error
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
