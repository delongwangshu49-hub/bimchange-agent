"""PySide6 desktop shell for the bounded Windows product."""

from __future__ import annotations

import html
import json
import shutil
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QObject,
    QPointF,
    Property,
    QPropertyAnimation,
    QRectF,
    QSize,
    QSettings,
    QSignalBlocker,
    QStandardPaths,
    Qt,
    QThread,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QColor,
    QCloseEvent,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QKeyEvent,
    QMouseEvent,
    QMovie,
    QPaintEvent,
    QPainter,
    QPixmap,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
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
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .ai_providers import (
    ProviderConfigurationError,
    ProviderRequestError,
    ProviderSettings,
    create_explanation_provider,
    default_provider_settings,
    provider_catalog,
    provider_descriptor,
)
from .desktop_design import (
    SUPPORTED_LANGUAGES,
    SUPPORTED_THEMES,
    stylesheet,
    text,
)
from .r3_product import diff_ifc_pair_r3
from .product_core import (
    ProductBoundaryError,
    load_json,
)
from .reporting import write_html_report


APP_NAME = "BIMChange-Agent"
DISPLAY_VERSION = "0.9.0"
HTML_REPORT_FILE_NAME = "report.html"
APP_ICON_PATH = (
    Path(__file__).resolve().parent
    / "resources"
    / "branding"
    / "bimchange-app-icon.png"
)
BRAND_ANIMATION_PATH = APP_ICON_PATH.with_name("bimchange-logo-evolution.gif")


def _ai_explanation_html(
    explanation: dict[str, Any], language: str
) -> str:
    """Turn structured provider output into readable, localized report prose."""

    content = explanation.get("explanation", explanation)
    if not isinstance(content, dict):
        content = {}

    def escaped(value: Any) -> str:
        return html.escape(str(value or "—"), quote=True)

    def items(field: str, empty_key: str) -> str:
        values = content.get(field, [])
        if not isinstance(values, list):
            values = []
        entries = "".join(
            f"<li>{escaped(value)}</li>"
            for value in values
            if isinstance(value, str) and value.strip()
        )
        return f"<ul>{entries}</ul>" if entries else f"<p>{text(language, empty_key)}</p>"

    provider = escaped(explanation.get("provider", "AI"))
    model = escaped(explanation.get("model", "—"))
    rational = content.get("rational_analysis")
    if not isinstance(rational, str) or not rational.strip():
        rational = text(language, "ai_rational_unavailable")
    return f"""
    <style>
      body {{ margin: 0; line-height: 1.55; }}
      h3 {{ margin: 14px 0 6px; font-size: 15px; }}
      p {{ margin: 4px 0 10px; }}
      ul {{ margin: 5px 0 12px; padding-left: 22px; }}
      li {{ margin: 0 0 5px; }}
      .meta {{ opacity: 0.72; font-size: 12px; }}
      .disclaimer {{ margin-top: 16px; padding: 10px 12px; border-left: 3px solid #8E4E36; }}
    </style>
    <p class="meta">{text(language, "ai_generated_by", provider=provider, model=model)}</p>
    <h3>{text(language, "ai_summary_heading")}</h3>
    <p>{escaped(content.get("summary"))}</p>
    <h3>{text(language, "ai_rational_heading")}</h3>
    <p>{escaped(rational)}</p>
    <h3>{text(language, "ai_key_changes_heading")}</h3>
    {items("key_changes", "ai_no_key_changes")}
    <h3>{text(language, "ai_limitations_heading")}</h3>
    {items("limitations", "ai_no_limitations")}
    <p class="disclaimer">{text(language, "ai_disclaimer")}</p>
    """


def _friendly_error_message(error: Exception, language: str = "zh_CN") -> str:
    if isinstance(error, ProductBoundaryError):
        return str(error)
    if isinstance(error, OSError):
        return text(language, "friendly_os_error")
    if isinstance(error, (json.JSONDecodeError, TypeError, ValueError)):
        return text(language, "friendly_format_error", error=error)
    return text(
        language, "friendly_unexpected", name=error.__class__.__name__
    )


def _provider_error_message(
    error: ProviderConfigurationError | ProviderRequestError,
    provider_id: str,
    language: str,
) -> str:
    try:
        provider_name = provider_descriptor(provider_id).display_name
    except ProviderConfigurationError:
        provider_name = provider_id
    category = getattr(error, "category", "configuration")
    key = f"ai_error_{category}"
    translated = text(
        language,
        key,
        provider=provider_name,
        status=getattr(error, "status_code", None) or "—",
    )
    return str(error) if translated == key else translated


@dataclass
class DesktopAISettings:
    enabled: bool = False
    provider_id: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    api_key: str = ""


@dataclass
class DesktopPreferences:
    """Non-secret preferences that may be persisted locally."""

    language: str = "zh_CN"
    theme: str = "system"


class AnimatedBrandMark(QWidget):
    """Compact brand motion for hover, analysis progress, and completion."""

    def __init__(
        self, image_path: Path, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._pixmap = QPixmap(str(image_path))
        self._motion = 0.0
        self._busy = False
        self.setFixedSize(46, 46)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(APP_NAME)
        self.setToolTip(APP_NAME)
        self._animation = QPropertyAnimation(self, b"motion", self)

    @Property(float)
    def motion(self) -> float:
        return self._motion

    @motion.setter
    def motion(self, value: float) -> None:
        self._motion = max(0.0, min(1.0, float(value)))
        self.update()

    @property
    def busy(self) -> bool:
        return self._busy

    def _animate_to(self, target: float, duration: int = 220) -> None:
        self._animation.stop()
        self._animation.setLoopCount(1)
        self._animation.setDuration(duration)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.setStartValue(self._motion)
        self._animation.setEndValue(target)
        self._animation.start()

    def setBusy(self, busy: bool) -> None:
        busy = bool(busy)
        if busy == self._busy:
            return
        self._busy = busy
        self._animation.stop()
        if busy:
            self._animation.setLoopCount(-1)
            self._animation.setDuration(1280)
            self._animation.setEasingCurve(QEasingCurve.Type.InOutSine)
            self._animation.setStartValue(0.0)
            self._animation.setKeyValueAt(0.5, 1.0)
            self._animation.setEndValue(0.0)
            self._animation.start()
        else:
            self._animate_to(0.0)

    def playCompletion(self) -> None:
        self._busy = False
        self._animation.stop()
        self._animation.setLoopCount(1)
        self._animation.setDuration(420)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.setStartValue(0.0)
        self._animation.setKeyValueAt(0.45, 1.0)
        self._animation.setEndValue(0.0)
        self._animation.start()

    def isAnimating(self) -> bool:
        return self._animation.state() == QAbstractAnimation.State.Running

    def enterEvent(self, event: object) -> None:
        if not self._busy:
            self._animate_to(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event: object) -> None:
        if not self._busy:
            self._animate_to(0.0)
        super().leaveEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        if self._pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        scale = 1.0 + self._motion * 0.045
        side = 40.0 * scale
        target = QRectF(
            (self.width() - side) / 2.0,
            (self.height() - side) / 2.0 - self._motion * 1.5,
            side,
            side,
        )
        painter.drawPixmap(
            target,
            self._pixmap,
            QRectF(0, 0, self._pixmap.width(), self._pixmap.height()),
        )


class AnimatedSwitch(QWidget):
    """Accessible Windows-style switch with a short horizontal thumb animation."""

    toggled = Signal(bool)

    def __init__(
        self, checked: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._checked = checked
        self._position = 1.0 if checked else 0.0
        self._theme = "light"
        self.setFixedSize(52, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._animation = QPropertyAnimation(self, b"position", self)
        self._animation.setDuration(180)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        checked = bool(checked)
        if checked == self._checked:
            return
        self._checked = checked
        self._animation.stop()
        self._animation.setStartValue(self._position)
        self._animation.setEndValue(1.0 if checked else 0.0)
        self._animation.start()
        self.toggled.emit(checked)

    def setTheme(self, theme: str) -> None:
        self._theme = "dark" if theme == "dark" else "light"
        self.update()

    def _get_position(self) -> float:
        return self._position

    def _set_position(self, value: float) -> None:
        self._position = max(0.0, min(1.0, float(value)))
        self.update()

    position = Property(float, _get_position, _set_position)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(1.0 if self.isEnabled() else 0.48)
        off = QColor("#59606A" if self._theme == "dark" else "#A5A9AE")
        on = QColor("#B76849" if self._theme == "dark" else "#A45132")
        track = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(on if self._checked else off)
        painter.drawRoundedRect(track, 13.0, 13.0)
        knob_size = 22.0
        knob_x = 3.0 + self._position * (self.width() - knob_size - 6.0)
        painter.setBrush(QColor("#F7F7F4"))
        painter.drawEllipse(QPointF(knob_x + knob_size / 2, 14.0), 11.0, 11.0)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            self.isEnabled()
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.setChecked(not self._checked)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.setChecked(not self._checked)
            event.accept()
            return
        super().keyPressEvent(event)


class FileDropZone(QFrame):
    """Clickable and droppable IFC path selector."""

    path_changed = Signal(object)

    def __init__(
        self,
        index: str,
        title_key: str,
        subtitle_key: str,
        language: str = "zh_CN",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._path: Path | None = None
        self.language = language
        self.title_key = title_key
        self.subtitle_key = subtitle_key
        self.setAcceptDrops(True)
        self.setObjectName("dropZone")
        self.setMinimumHeight(210)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)
        self.index_label = QLabel(index)
        self.index_label.setObjectName("dropIndex")
        layout.addWidget(self.index_label)
        layout.addStretch()
        self.title_label = QLabel()
        self.title_label.setObjectName("dropTitle")
        layout.addWidget(self.title_label)
        self.detail_label = QLabel()
        self.detail_label.setWordWrap(True)
        self.detail_label.setObjectName("dropDetail")
        layout.addWidget(self.detail_label)
        self.select_button = QPushButton()
        self.select_button.setObjectName("secondaryButton")
        self.select_button.clicked.connect(self.choose_file)
        layout.addWidget(self.select_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()
        self.retranslate_ui()

    @property
    def path(self) -> Path | None:
        return self._path

    @staticmethod
    def accepts_path(path: Path) -> bool:
        return path.is_file() and path.suffix.lower() == ".ifc"

    def set_file(self, path: Path) -> None:
        path = path.expanduser().resolve()
        if not self.accepts_path(path):
            raise ValueError(text(self.language, "invalid_ifc"))
        self._path = path
        size_mib = path.stat().st_size / 1024 / 1024
        self.detail_label.setText(f"{path.name}\n{size_mib:.2f} MiB")
        self.select_button.setText(text(self.language, "replace_ifc"))
        self.setProperty("hasFile", True)
        self.style().unpolish(self)
        self.style().polish(self)
        self.path_changed.emit(path)

    @Slot()
    def choose_file(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self, text(self.language, "file_dialog"), "", "IFC Files (*.ifc)"
        )
        if selected:
            try:
                self.set_file(Path(selected))
            except (OSError, ValueError) as error:
                QMessageBox.warning(
                    self,
                    text(self.language, "file_selection_failed"),
                    _friendly_error_message(error, self.language),
                )

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
                QMessageBox.warning(
                    self,
                    text(self.language, "drop_failed"),
                    _friendly_error_message(error, self.language),
                )

    def set_language(self, language: str) -> None:
        self.language = language
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.title_label.setText(text(self.language, self.title_key))
        if self._path is None:
            self.detail_label.setText(text(self.language, self.subtitle_key))
            self.select_button.setText(text(self.language, "select_ifc"))
        else:
            try:
                size_mib = self._path.stat().st_size / 1024 / 1024
                detail = f"{self._path.name}\n{size_mib:.2f} MiB"
            except OSError:
                detail = self._path.name
            self.detail_label.setText(detail)
            self.select_button.setText(text(self.language, "replace_ifc"))


class AISettingsDialog(QDialog):
    """Unified settings center; secrets remain session-only."""

    def __init__(
        self,
        settings: DesktopAISettings,
        parent: QWidget | None = None,
        preferences: DesktopPreferences | None = None,
    ) -> None:
        super().__init__(parent)
        self._preferences = preferences or DesktopPreferences()
        self.language_code = self._preferences.language
        self.setWindowTitle(text(self.language_code, "settings_title"))
        self.setMinimumSize(560, 500)
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        general_page = QWidget()
        general_layout = QVBoxLayout(general_page)
        general_layout.setContentsMargins(20, 20, 20, 20)
        general_title = QLabel(text(self.language_code, "appearance_title"))
        general_title.setObjectName("sectionTitle")
        general_layout.addWidget(general_title)
        general_form = QFormLayout()
        self.theme = QComboBox()
        self.theme.addItem(text(self.language_code, "theme_system"), "system")
        self.theme.addItem(text(self.language_code, "theme_light"), "light")
        self.theme.addItem(text(self.language_code, "theme_dark"), "dark")
        self.theme.setCurrentIndex(max(0, self.theme.findData(self._preferences.theme)))
        general_form.addRow(text(self.language_code, "theme"), self.theme)
        self.language = QComboBox()
        self.language.addItem(text(self.language_code, "language_zh"), "zh_CN")
        self.language.addItem(text(self.language_code, "language_en"), "en")
        self.language.setCurrentIndex(
            max(0, self.language.findData(self._preferences.language))
        )
        general_form.addRow(text(self.language_code, "language"), self.language)
        general_layout.addLayout(general_form)
        restart_note = QLabel(text(self.language_code, "settings_restart_note"))
        restart_note.setObjectName("muted")
        general_layout.addWidget(restart_note)
        general_layout.addStretch()

        ai_page = QWidget()
        ai_layout = QVBoxLayout(ai_page)
        ai_layout.setContentsMargins(20, 20, 20, 20)
        ai_title = QLabel(text(self.language_code, "ai_settings_title"))
        ai_title.setObjectName("sectionTitle")
        ai_layout.addWidget(ai_title)
        enabled_row = QHBoxLayout()
        self.enabled = AnimatedSwitch(settings.enabled)
        self.enabled.setTheme(
            "dark" if self._preferences.theme == "dark" else "light"
        )
        self.enabled.setAccessibleName(text(self.language_code, "ai_enabled"))
        self.enabled_label = QLabel()
        self.enabled_label.setObjectName("aiStateLabel")
        self.enabled.toggled.connect(self._update_enabled_label)
        enabled_row.addWidget(self.enabled)
        enabled_row.addWidget(self.enabled_label)
        enabled_row.addStretch()
        ai_layout.addLayout(enabled_row)
        form = QFormLayout()
        self.provider = QComboBox()
        for descriptor in provider_catalog():
            self.provider.addItem(descriptor.display_name, descriptor.provider_id)
            if descriptor.status != "enabled":
                item = self.provider.model().item(self.provider.count() - 1)
                if item is not None:
                    item.setEnabled(False)
        current_index = self.provider.findData(settings.provider_id)
        self.provider.setCurrentIndex(max(0, current_index))
        form.addRow(text(self.language_code, "provider"), self.provider)
        self.base_url = QLineEdit(settings.base_url)
        self.base_url.setReadOnly(True)
        form.addRow(text(self.language_code, "base_url"), self.base_url)
        self.model = QLineEdit(settings.model)
        form.addRow(text(self.language_code, "model"), self.model)
        self.provider.currentIndexChanged.connect(self._provider_changed)
        self.api_key = QLineEdit(settings.api_key)
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText(text(self.language_code, "api_key_placeholder"))
        form.addRow(text(self.language_code, "api_key"), self.api_key)
        ai_layout.addLayout(form)
        note = QLabel(text(self.language_code, "ai_privacy_note"))
        note.setWordWrap(True)
        note.setObjectName("muted")
        ai_layout.addWidget(note)
        ai_layout.addStretch()
        self.tabs.addTab(general_page, text(self.language_code, "settings_general_tab"))
        self.tabs.addTab(ai_page, text(self.language_code, "settings_ai_tab"))
        layout.addWidget(self.tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button is not None:
            save_button.setText(text(self.language_code, "save"))
            save_button.setObjectName("primaryButton")
        if cancel_button is not None:
            cancel_button.setText(text(self.language_code, "cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._update_enabled_label(self.enabled.isChecked())

    def _update_enabled_label(self, enabled: bool) -> None:
        key = "ai_state_on" if enabled else "ai_state_off"
        self.enabled_label.setText(text(self.language_code, key))
        self.enabled_label.setProperty("enabledState", enabled)
        self.enabled_label.style().unpolish(self.enabled_label)
        self.enabled_label.style().polish(self.enabled_label)

    def _provider_changed(self) -> None:
        provider_id = str(self.provider.currentData())
        try:
            defaults = default_provider_settings(provider_id)
        except ProviderConfigurationError:
            return
        self.base_url.setText(defaults.base_url)
        self.model.setText(defaults.model)

    def settings(self) -> DesktopAISettings:
        enabled = self.enabled.isChecked()
        return DesktopAISettings(
            enabled=enabled,
            provider_id=str(self.provider.currentData()),
            base_url=self.base_url.text().strip(),
            model=self.model.text().strip(),
            api_key=self.api_key.text() if enabled else "",
        )

    def preferences(self) -> DesktopPreferences:
        return DesktopPreferences(
            language=str(self.language.currentData()),
            theme=str(self.theme.currentData()),
        )

    def accept(self) -> None:
        candidate = self.settings()
        if candidate.enabled:
            if not candidate.model or not candidate.api_key.strip():
                QMessageBox.warning(
                    self,
                    text(self.language_code, "settings_invalid"),
                    text(self.language_code, "ai_fields_required"),
                )
                return
            try:
                create_explanation_provider(
                    ProviderSettings(
                        provider_id=candidate.provider_id,
                        base_url=candidate.base_url,
                        model=candidate.model,
                    )
                )
            except ProviderConfigurationError as error:
                QMessageBox.warning(
                    self, text(self.language_code, "settings_invalid"), str(error)
                )
                return
        super().accept()


class FileSelectionPage(QWidget):
    start_requested = Signal()

    def __init__(
        self, language: str = "zh_CN", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.language = language
        layout = QVBoxLayout(self)
        layout.setContentsMargins(52, 38, 52, 42)
        layout.setSpacing(16)
        self.eyebrow = QLabel()
        self.eyebrow.setObjectName("eyebrow")
        layout.addWidget(self.eyebrow)
        self.title = QLabel()
        self.title.setObjectName("pageTitle")
        layout.addWidget(self.title)
        self.subtitle = QLabel()
        self.subtitle.setObjectName("pageSubtitle")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)
        self.preview_note = QLabel()
        self.preview_note.setObjectName("previewNote")
        layout.addWidget(self.preview_note, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addSpacing(8)
        zones = QHBoxLayout()
        zones.setSpacing(18)
        self.source_zone = FileDropZone(
            "A", "source_title", "source_subtitle", language
        )
        self.revised_zone = FileDropZone(
            "B", "revised_title", "revised_subtitle", language
        )
        zones.addWidget(self.source_zone)
        zones.addWidget(self.revised_zone)
        layout.addLayout(zones)
        footer = QHBoxLayout()
        self.boundary = QLabel()
        self.boundary.setObjectName("muted")
        footer.addWidget(self.boundary)
        footer.addStretch()
        self.start_button = QPushButton()
        self.start_button.setObjectName("primaryButton")
        self.start_button.setMinimumHeight(46)
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_requested)
        footer.addWidget(self.start_button)
        layout.addLayout(footer)
        self.privacy_note = QLabel()
        self.privacy_note.setObjectName("muted")
        self.privacy_note.setWordWrap(True)
        layout.addWidget(self.privacy_note)
        self.source_zone.path_changed.connect(self._update_ready)
        self.revised_zone.path_changed.connect(self._update_ready)
        self.retranslate_ui()

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

    def set_language(self, language: str) -> None:
        self.language = language
        self.source_zone.set_language(language)
        self.revised_zone.set_language(language)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.eyebrow.setText(text(self.language, "home_eyebrow"))
        self.title.setText(text(self.language, "home_title"))
        self.subtitle.setText(text(self.language, "home_subtitle"))
        self.preview_note.setText(text(self.language, "preview_note"))
        self.boundary.setText(text(self.language, "boundary"))
        self.start_button.setText(text(self.language, "start_analysis"))
        self.privacy_note.setText(text(self.language, "privacy_note"))


class ReportPage(QWidget):
    new_analysis_requested = Signal()

    def __init__(
        self, language: str = "zh_CN", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.language = language
        self.artifact_path: Path | None = None
        self.html_path: Path | None = None
        self.artifact: dict[str, Any] | None = None
        self.all_changes: list[dict[str, Any]] = []
        self.explanation: dict[str, Any] | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 28)
        layout.setSpacing(12)
        top = QHBoxLayout()
        heading = QVBoxLayout()
        self.eyebrow = QLabel()
        self.eyebrow.setObjectName("eyebrow")
        heading.addWidget(self.eyebrow)
        self.title = QLabel()
        self.title.setObjectName("pageTitle")
        heading.addWidget(self.title)
        self.file_pair = QLabel()
        self.file_pair.setObjectName("pageSubtitle")
        heading.addWidget(self.file_pair)
        top.addLayout(heading)
        top.addStretch()
        self.new_button = QPushButton()
        self.new_button.clicked.connect(self.new_analysis_requested)
        top.addWidget(self.new_button)
        layout.addLayout(top)

        cards = QGridLayout()
        self.card_labels: dict[str, QLabel] = {}
        card_specs = (
            ("total_supported", "metric_total"),
            ("added", "metric_added"),
            ("deleted", "metric_deleted"),
            ("property_modified", "metric_modified"),
            ("geometry_modified", "metric_geometry"),
            ("relationship_modified", "metric_relationship"),
            ("unsupported", "metric_unsupported"),
        )
        self.card_captions: dict[str, QLabel] = {}
        for column, (key, label_key) in enumerate(card_specs):
            frame = QFrame()
            frame.setObjectName("summaryCard")
            frame.setProperty("metricKind", key)
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(15, 12, 15, 12)
            caption = QLabel()
            caption.setObjectName("muted")
            value = QLabel("0")
            value.setObjectName("summaryValue")
            frame_layout.addWidget(caption)
            frame_layout.addWidget(value)
            cards.addWidget(frame, 0, column)
            self.card_labels[key] = value
            self.card_captions[label_key] = caption
        layout.addLayout(cards)

        filter_frame = QFrame()
        filter_frame.setObjectName("filterBar")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(12, 10, 12, 10)
        self.search_filter = QLineEdit()
        self.search_filter.setClearButtonEnabled(True)
        self.search_filter.textChanged.connect(self._refresh_table)
        filter_layout.addWidget(self.search_filter, stretch=2)
        self.type_filter = QComboBox()
        self.type_filter.currentIndexChanged.connect(self._refresh_table)
        filter_layout.addWidget(self.type_filter)
        self.entity_filter = QComboBox()
        self.entity_filter.currentIndexChanged.connect(self._refresh_table)
        filter_layout.addWidget(self.entity_filter)
        self.storey_filter = QComboBox()
        self.storey_filter.currentIndexChanged.connect(self._refresh_table)
        filter_layout.addWidget(self.storey_filter)
        layout.addWidget(filter_frame)

        self.result_count = QLabel()
        self.result_count.setObjectName("resultCount")
        layout.addWidget(self.result_count)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setOpaqueResize(False)
        self.splitter.setHandleWidth(11)
        self.splitter.splitterMoved.connect(self._clamp_splitter)
        self.table = QTableWidget(0, 5)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.table.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.table.verticalScrollBar().setSingleStep(18)
        self.table.horizontalScrollBar().setSingleStep(24)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setMinimumSectionSize(72)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._update_detail)
        self.splitter.addWidget(self.table)

        self.review_tabs = QTabWidget()
        self.review_tabs.setObjectName("reviewTabs")
        self.review_tabs.setMinimumWidth(300)
        detail_page = QWidget()
        detail_layout = QVBoxLayout(detail_page)
        detail_layout.setContentsMargins(14, 12, 14, 12)
        self.detail_body = QTextBrowser()
        self.detail_body.setFrameShape(QFrame.Shape.NoFrame)
        self.detail_body.verticalScrollBar().setSingleStep(18)
        self.detail_body.horizontalScrollBar().setSingleStep(24)
        detail_layout.addWidget(self.detail_body)

        ai_page = QWidget()
        ai_layout = QVBoxLayout(ai_page)
        ai_layout.setContentsMargins(14, 12, 14, 12)
        self.ai_output = QTextBrowser()
        self.ai_output.setFrameShape(QFrame.Shape.NoFrame)
        self.ai_output.verticalScrollBar().setSingleStep(18)
        self.ai_output.horizontalScrollBar().setSingleStep(24)
        ai_layout.addWidget(self.ai_output)
        self.review_tabs.addTab(detail_page, "")
        self.review_tabs.addTab(ai_page, "")
        self.splitter.addWidget(self.review_tabs)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        self._configure_splitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter, stretch=1)

        actions = QHBoxLayout()
        self.export_json = QPushButton()
        self.export_html = QPushButton()
        self.open_folder = QPushButton()
        self.export_json.clicked.connect(self._export_json)
        self.export_html.clicked.connect(self._export_html)
        self.open_folder.clicked.connect(self._open_folder)
        actions.addWidget(self.export_json)
        actions.addWidget(self.export_html)
        actions.addWidget(self.open_folder)
        actions.addStretch()
        layout.addLayout(actions)
        self.retranslate_ui()
        self._populate_filters()
        self.ai_output.setPlainText(text(self.language, "ai_disabled_report"))

    def load_report(
        self,
        artifact: dict[str, Any],
        artifact_path: Path,
        html_path: Path,
        explanation: dict[str, Any] | None,
    ) -> None:
        self.artifact_path = artifact_path
        self.html_path = html_path
        self.artifact = artifact
        self.all_changes = list(artifact["changes"])
        self.explanation = explanation
        self.file_pair.setText(
            f"{artifact['source']['file_name']}  →  {artifact['revised']['file_name']}"
        )
        for key, label in self.card_labels.items():
            label.setText(str(artifact["summary"].get(key, 0)))
        self._populate_filters()
        self._refresh_table()
        if explanation is None:
            self.ai_output.setPlainText(text(self.language, "ai_disabled_report"))
        else:
            self.ai_output.setHtml(_ai_explanation_html(explanation, self.language))

    def _populate_filters(self) -> None:
        current = (
            self.type_filter.currentData(),
            self.entity_filter.currentData(),
            self.storey_filter.currentData(),
        )
        blockers = (
            QSignalBlocker(self.type_filter),
            QSignalBlocker(self.entity_filter),
            QSignalBlocker(self.storey_filter),
        )
        self.type_filter.clear()
        self.type_filter.addItem(text(self.language, "filter_all_types"), "")
        for value in sorted({item["change_type"] for item in self.all_changes}):
            self.type_filter.addItem(self._display_change_type(value), value)
        self.entity_filter.clear()
        self.entity_filter.addItem(text(self.language, "filter_all_entities"), "")
        for value in sorted({item["entity_type"] for item in self.all_changes}):
            self.entity_filter.addItem(value, value)
        self.storey_filter.clear()
        self.storey_filter.addItem(text(self.language, "filter_all_storeys"), "")
        storeys = {
            storey["name"]
            for item in self.all_changes
            if (storey := item["location"]["building_storey"]) is not None
        }
        for value in sorted(storeys):
            self.storey_filter.addItem(value, value)
        for combo, selected in zip(
            (self.type_filter, self.entity_filter, self.storey_filter), current
        ):
            index = combo.findData(selected)
            combo.setCurrentIndex(max(0, index))
        del blockers

    def _refresh_table(self, *_args: object) -> None:
        query = self.search_filter.text().strip().casefold()
        change_type = str(self.type_filter.currentData() or "")
        entity_type = str(self.entity_filter.currentData() or "")
        storey_name = str(self.storey_filter.currentData() or "")
        visible: list[tuple[int, dict[str, Any]]] = []
        for index, change in enumerate(self.all_changes):
            storey = change["location"]["building_storey"]
            field_text = self._display_field(change)
            geometry = change.get("geometry_change")
            relationship = change.get("relationship_change")
            geometry_search = ""
            if isinstance(geometry, dict):
                geometry_search = " ".join(
                    (
                        str(geometry.get("subtype", "")),
                        self._display_value(geometry.get("delta")),
                        self._display_value(geometry.get("distance")),
                    )
                )
            relationship_search = ""
            if isinstance(relationship, dict):
                relationship_search = " ".join(
                    (
                        str(relationship.get("subtype", "")),
                        str(relationship.get("relationship", "")),
                        self._display_value(relationship.get("old_relation")),
                        self._display_value(relationship.get("new_relation")),
                    )
                )
            searchable = " ".join(
                (
                    change["change_type"],
                    self._display_change_type(change["change_type"]),
                    change["entity_type"],
                    change["global_id"],
                    storey["name"] if storey else "",
                    field_text,
                    geometry_search,
                    relationship_search,
                    self._display_value(change["old_value"]),
                    self._display_value(change["new_value"]),
                )
            ).casefold()
            if query and query not in searchable:
                continue
            if change_type and change["change_type"] != change_type:
                continue
            if entity_type and change["entity_type"] != entity_type:
                continue
            if storey_name and (storey is None or storey["name"] != storey_name):
                continue
            visible.append((index, change))

        self.table.setUpdatesEnabled(False)
        selection_blocker = QSignalBlocker(self.table)
        try:
            self.table.setRowCount(len(visible))
            for row, (change_index, change) in enumerate(visible):
                storey = change["location"]["building_storey"]
                values = (
                    self._display_change_type(change["change_type"]),
                    change["entity_type"],
                    change["global_id"],
                    storey["name"] if storey else "—",
                    self._display_field(change),
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setData(Qt.ItemDataRole.UserRole, change_index)
                    item.setToolTip(value)
                    self.table.setItem(row, column, item)
            if visible:
                self.table.selectRow(0)
            else:
                self.table.clearSelection()
        finally:
            del selection_blocker
            self.table.setUpdatesEnabled(True)
            self.table.viewport().update()
        self.result_count.setText(
            text(
                self.language,
                "results_count",
                visible=len(visible),
                total=len(self.all_changes),
            )
        )
        if visible:
            self._update_detail()
        else:
            self.detail_body.setPlainText(text(self.language, "detail_empty"))

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Give the change table full width before asking users to scroll sideways."""
        vertical = event.size().width() < 1080
        requested = (
            Qt.Orientation.Vertical if vertical else Qt.Orientation.Horizontal
        )
        if self.splitter.orientation() != requested:
            self.splitter.setOrientation(requested)
            self._configure_splitter(requested)
        super().resizeEvent(event)
        QTimer.singleShot(0, self._clamp_splitter)

    def _configure_splitter(self, orientation: Qt.Orientation) -> None:
        """Apply usable panel bounds whenever the responsive axis changes."""

        if orientation == Qt.Orientation.Vertical:
            self.table.setMinimumWidth(0)
            self.review_tabs.setMinimumWidth(0)
            self.table.setMinimumHeight(100)
            self.review_tabs.setMinimumHeight(100)
            self.splitter.setSizes([360, 170])
        else:
            self.table.setMinimumHeight(0)
            self.review_tabs.setMinimumHeight(0)
            self.table.setMinimumWidth(520)
            self.review_tabs.setMinimumWidth(340)
            self.splitter.setSizes([860, 380])
        QTimer.singleShot(0, self._clamp_splitter)

    @Slot()
    @Slot(int, int)
    def _clamp_splitter(self, *_args: object) -> None:
        """Keep either pane from being dragged outside its usable boundary."""

        sizes = self.splitter.sizes()
        if len(sizes) != 2:
            return
        total = sum(sizes)
        if self.splitter.orientation() == Qt.Orientation.Vertical:
            primary_min, review_min = 100, 100
        else:
            primary_min, review_min = 520, 340
        if total < primary_min + review_min:
            return
        primary = max(primary_min, min(sizes[0], total - review_min))
        bounded = [primary, total - primary]
        if bounded != sizes:
            with QSignalBlocker(self.splitter):
                self.splitter.setSizes(bounded)

    def _update_detail(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            self.detail_body.setPlainText(text(self.language, "detail_empty"))
            return
        change_index = selected[0].data(Qt.ItemDataRole.UserRole)
        if not isinstance(change_index, int) or change_index >= len(self.all_changes):
            self.detail_body.setPlainText(text(self.language, "detail_empty"))
            return
        change = self.all_changes[change_index]
        storey = change["location"]["building_storey"]
        geometry = change.get("geometry_change")
        relationship = change.get("relationship_change")
        evidence = change.get("evidence", {})
        evidence_selector = evidence.get("selector", "—")
        if isinstance(evidence_selector, (dict, list)):
            evidence_selector = json.dumps(
                evidence_selector, ensure_ascii=False, sort_keys=True
            )
        rows = [
            ("detail_change", self._display_change_type(change["change_type"])),
            ("detail_entity", change["entity_type"]),
            ("detail_guid", change["global_id"]),
            ("detail_storey", storey["name"] if storey else "—"),
            ("detail_field", self._display_field(change)),
            ("detail_old", self._display_value(change["old_value"])),
            ("detail_new", self._display_value(change["new_value"])),
            ("detail_evidence", str(evidence_selector)),
        ]
        if isinstance(geometry, dict):
            rows.append(("detail_geometry_subtype", self._display_geometry_subtype(geometry["subtype"])))
            if geometry["subtype"] == "placement_translation":
                rows.extend((("detail_delta", self._display_value(geometry["delta"])), ("detail_distance", self._display_value(geometry["distance"]))))
            elif geometry["subtype"] == "extrusion_dimension_change":
                rows.append(("detail_delta", self._display_value(geometry["changed_dimensions"])))
            else:
                rows.extend((("detail_delta", self._display_value(geometry["changed_vertex_count"])), ("detail_distance", self._display_value(geometry["max_vertex_displacement_m"]))))
            rows.append(("detail_unit", str(geometry["length_unit"])))
        if isinstance(relationship, dict):
            rows.append(("detail_relationship_subtype", self._display_relationship_subtype(relationship["subtype"])))
        self.detail_body.setPlainText(
            "\n\n".join(f"{text(self.language, key)}\n{value}" for key, value in rows)
        )

    def _display_change_type(self, value: str) -> str:
        key = f"change_{value}"
        translated = text(self.language, key)
        return value if translated == key else translated

    def _display_geometry_subtype(self, value: str) -> str:
        key = f"geometry_{value}"
        translated = text(self.language, key)
        return value if translated == key else translated

    def _display_relationship_subtype(self, value: str) -> str:
        key = f"relationship_{value}"
        translated = text(self.language, key)
        return value if translated == key else translated

    def _display_field(self, change: dict[str, Any]) -> str:
        field = change["field"]
        if field is not None:
            return f"{field['property_set']}.{field['name']}"
        geometry = change.get("geometry_change")
        if isinstance(geometry, dict):
            if geometry["subtype"] == "placement_translation":
                return (
                    f"{self._display_geometry_subtype(geometry['subtype'])} · "
                    f"Δ {self._display_value(geometry['delta'])} {geometry['length_unit']} · "
                    f"{self._display_value(geometry['distance'])} {geometry['length_unit']}"
                )
            if geometry["subtype"] == "extrusion_dimension_change":
                fields = ", ".join(item["field"] for item in geometry["changed_dimensions"])
                return f"{self._display_geometry_subtype(geometry['subtype'])} · {fields}"
            return (
                f"{self._display_geometry_subtype(geometry['subtype'])} · "
                f"{geometry['changed_vertex_count']} vertices · max Δ {geometry['max_vertex_displacement_m']} m"
            )
        relationship = change.get("relationship_change")
        if isinstance(relationship, dict):
            return self._display_relationship_subtype(relationship["subtype"])
        return "—"

    def set_language(self, language: str) -> None:
        self.language = language
        self.retranslate_ui()
        self._populate_filters()
        if self.artifact is not None:
            self._refresh_table()
        if self.explanation is None:
            self.ai_output.setPlainText(text(self.language, "ai_disabled_report"))
        else:
            self.ai_output.setHtml(
                _ai_explanation_html(self.explanation, self.language)
            )

    def retranslate_ui(self) -> None:
        self.eyebrow.setText(text(self.language, "report_eyebrow"))
        self.title.setText(text(self.language, "report_title"))
        self.new_button.setText(text(self.language, "new_analysis"))
        for label_key, label in self.card_captions.items():
            label.setText(text(self.language, label_key))
        self.search_filter.setPlaceholderText(text(self.language, "filter_search"))
        self.table.setHorizontalHeaderLabels(
            [
                text(self.language, "table_type"),
                text(self.language, "table_entity"),
                text(self.language, "table_guid"),
                text(self.language, "table_storey"),
                text(self.language, "table_field"),
            ]
        )
        self.review_tabs.setTabText(0, text(self.language, "detail_title"))
        self.review_tabs.setTabText(1, text(self.language, "ai_output_title"))
        self.export_json.setText(text(self.language, "export_json"))
        self.export_html.setText(text(self.language, "export_html"))
        self.open_folder.setText(text(self.language, "open_folder"))
        if not self.all_changes:
            self.result_count.setText(
                text(self.language, "results_count", visible=0, total=0)
            )
            self.detail_body.setPlainText(text(self.language, "detail_empty"))

    @staticmethod
    def _display_value(value: Any) -> str:
        if value is None:
            return "—"
        if isinstance(value, (dict, list, bool, int, float)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return str(value)

    def _copy_report(self, source: Path | None, title: str, pattern: str) -> None:
        if source is None:
            QMessageBox.warning(
                self,
                text(self.language, "export_unavailable"),
                text(self.language, "export_unavailable_body"),
            )
            return
        target, _ = QFileDialog.getSaveFileName(self, title, source.name, pattern)
        if target:
            try:
                target_path = Path(target).expanduser().resolve()
                if source.resolve() == target_path:
                    QMessageBox.information(
                        self,
                        text(self.language, "same_export"),
                        text(self.language, "same_export_body"),
                    )
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
                QMessageBox.critical(
                    self,
                    text(self.language, "export_failed"),
                    _friendly_error_message(error, self.language),
                )

    @Slot()
    def _export_json(self) -> None:
        self._copy_report(
            self.artifact_path,
            text(self.language, "export_json_title"),
            "JSON Files (*.json)",
        )

    @Slot()
    def _export_html(self) -> None:
        self._copy_report(
            self.html_path,
            text(self.language, "export_html_title"),
            "HTML Files (*.html)",
        )

    @Slot()
    def _open_folder(self) -> None:
        if self.artifact_path is not None:
            opened = QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(self.artifact_path.parent))
            )
            if not opened:
                QMessageBox.warning(
                    self,
                    text(self.language, "open_failed"),
                    text(self.language, "open_failed_body"),
                )
        else:
            QMessageBox.warning(
                self,
                text(self.language, "open_failed"),
                text(self.language, "no_report_folder"),
            )


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
        language: str = "zh_CN",
    ) -> None:
        super().__init__()
        self.source = source
        self.revised = revised
        self.output_dir = output_dir
        self.ai_settings = ai_settings
        self.language = language

    @Slot()
    def run(self) -> None:
        try:
            self.progress.emit(text(self.language, "progress_compare"))
            result = diff_ifc_pair_r3(
                self.source, self.revised, self.output_dir
            )
            artifact_path = Path(result["change_records"])
            artifact = load_json(artifact_path)
            explanation = None
            if self.ai_settings.enabled:
                self.progress.emit(text(self.language, "progress_ai"))
                try:
                    provider = create_explanation_provider(
                        ProviderSettings(
                            provider_id=self.ai_settings.provider_id,
                            base_url=self.ai_settings.base_url,
                            model=self.ai_settings.model,
                        )
                    )
                    explanation = provider.explain(
                        artifact,
                        api_key=self.ai_settings.api_key,
                        language=self.language,
                    )
                except (ProviderConfigurationError, ProviderRequestError) as error:
                    reason = _provider_error_message(
                        error, self.ai_settings.provider_id, self.language
                    )
                    explanation = {
                        "provider": self.ai_settings.provider_id,
                        "model": self.ai_settings.model,
                        "status": "ERROR",
                        "error_category": getattr(error, "category", "configuration"),
                        "error": reason,
                        "explanation": {
                            "summary": text(self.language, "ai_failed_body"),
                            "key_changes": [],
                            "rational_analysis": text(
                                self.language, "ai_rational_unavailable"
                            ),
                            "limitations": [
                                text(
                                    self.language,
                                    "ai_failed_reason",
                                    reason=reason,
                                )
                            ],
                        },
                    }
                except Exception as error:
                    reason = text(
                        self.language,
                        "friendly_unexpected",
                        name=error.__class__.__name__,
                    )
                    explanation = {
                        "provider": self.ai_settings.provider_id,
                        "model": self.ai_settings.model,
                        "status": "ERROR",
                        "error_category": "unexpected",
                        "error": reason,
                        "explanation": {
                            "summary": text(self.language, "ai_failed_body"),
                            "key_changes": [],
                            "rational_analysis": text(
                                self.language, "ai_rational_unavailable"
                            ),
                            "limitations": [reason],
                        },
                    }
            self.progress.emit(text(self.language, "progress_report"))
            html_path = write_html_report(
                artifact,
                self.output_dir / HTML_REPORT_FILE_NAME,
                explanation=explanation,
                language=self.language,
            )
            self.finished.emit(artifact, artifact_path, html_path, explanation)
        except Exception as error:
            self.failed.emit(_friendly_error_message(error, self.language))


class BrandSplash(QWidget):
    """Play the checked-in brand animation once before revealing the workspace."""

    finished = Signal()

    def __init__(self, animation_path: Path = BRAND_ANIMATION_PATH) -> None:
        super().__init__(
            None,
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setObjectName("brandSplash")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setStyleSheet("#brandSplash { background: #E7E8E4; }")
        self._finishing = False
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(180)
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(self._complete)

        screen = QApplication.primaryScreen()
        available_width = screen.availableGeometry().width() if screen else 1200
        width = max(560, min(720, available_width - 120))
        height = round(width * 360 / 1120)
        self.setFixedSize(QSize(width, height))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.animation_label = QLabel()
        self.animation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.animation_label)

        self.movie = QMovie(str(animation_path))
        self.movie.setCacheMode(QMovie.CacheMode.CacheAll)
        self.movie.frameChanged.connect(self._frame_changed)

    def start(self) -> None:
        if not self.movie.isValid():
            QTimer.singleShot(0, self._complete)
            return
        self.movie.start()

    @Slot(int)
    def _frame_changed(self, frame_number: int) -> None:
        frame = self.movie.currentPixmap()
        if not frame.isNull():
            scale = max(1.0, self.devicePixelRatioF())
            target = QSize(
                round(self.animation_label.width() * scale),
                round(self.animation_label.height() * scale),
            )
            frame = frame.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            frame.setDevicePixelRatio(scale)
            self.animation_label.setPixmap(frame)
        frame_count = self.movie.frameCount()
        if self._finishing or frame_count <= 0 or frame_number < frame_count - 1:
            return
        self._finishing = True
        self.movie.stop()
        QTimer.singleShot(100, self._fade.start)

    @Slot()
    def _complete(self) -> None:
        if not self._finishing:
            self._finishing = True
            self.movie.stop()
        self.finished.emit()
        self.close()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(
            area.center().x() - self.width() // 2,
            area.center().y() - self.height() // 2,
        )


class MainWindow(QMainWindow):
    def __init__(
        self,
        report_root: Path | None = None,
        preferences: DesktopPreferences | None = None,
        persist_preferences: bool = True,
    ) -> None:
        super().__init__()
        self.resize(1120, 720)
        self.setMinimumSize(880, 600)
        if APP_ICON_PATH.is_file():
            self.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        self._settings_store = (
            QSettings("BIMChange-Agent", "BIMChange-Agent")
            if persist_preferences
            else None
        )
        self.preferences = preferences or self._load_preferences()
        self.ai_settings = self._load_ai_settings()
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
        header_layout.setContentsMargins(24, 10, 28, 10)
        self.brand_mark = AnimatedBrandMark(APP_ICON_PATH)
        header_layout.addWidget(self.brand_mark)
        identity = QVBoxLayout()
        identity.setSpacing(2)
        self.brand = QLabel()
        self.brand.setObjectName("brand")
        identity.addWidget(self.brand)
        self.product_descriptor = QLabel()
        self.product_descriptor.setObjectName("productDescriptor")
        identity.addWidget(self.product_descriptor)
        header_layout.addLayout(identity)
        header_layout.addStretch()
        self.ai_toggle = AnimatedSwitch(self.ai_settings.enabled)
        self.ai_toggle.setAccessibleName(text(self.preferences.language, "ai_toggle"))
        self.ai_toggle.toggled.connect(self._on_ai_toggled)
        header_layout.addWidget(self.ai_toggle)
        self.ai_toggle_label = QLabel()
        self.ai_toggle_label.setObjectName("aiStateLabel")
        header_layout.addWidget(self.ai_toggle_label)
        self.ai_status = self.ai_toggle
        self.settings_button = QPushButton()
        self.settings_button.clicked.connect(self.open_ai_settings)
        header_layout.addWidget(self.settings_button)
        outer.addWidget(header)

        step_rail = QFrame()
        step_rail.setObjectName("stepRail")
        step_layout = QHBoxLayout(step_rail)
        step_layout.setContentsMargins(28, 9, 28, 9)
        step_layout.setSpacing(28)
        self.step_labels: list[QLabel] = []
        for _ in range(3):
            step = QLabel()
            step.setObjectName("stepLabel")
            step_layout.addWidget(step)
            self.step_labels.append(step)
        step_layout.addStretch()
        outer.addWidget(step_rail)

        self.stack = QStackedWidget()
        self.file_page = FileSelectionPage(self.preferences.language)
        self.report_page = ReportPage(self.preferences.language)
        self.stack.addWidget(self.file_page)
        self.stack.addWidget(self.report_page)
        self.stack.currentChanged.connect(self._stack_changed)
        outer.addWidget(self.stack, stretch=1)

        self.progress_panel = QFrame()
        self.progress_panel.setObjectName("progressPanel")
        progress_layout = QHBoxLayout(self.progress_panel)
        progress_layout.setContentsMargins(28, 12, 28, 12)
        self.progress_label = QLabel()
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
        self.retranslate_ui()
        self.apply_theme()
        self._set_step(0)

    def _load_preferences(self) -> DesktopPreferences:
        if self._settings_store is None:
            return DesktopPreferences()
        language = str(self._settings_store.value("appearance/language", "zh_CN"))
        theme = str(self._settings_store.value("appearance/theme", "system"))
        return DesktopPreferences(
            language=language if language in SUPPORTED_LANGUAGES else "zh_CN",
            theme=theme if theme in SUPPORTED_THEMES else "system",
        )

    def _load_ai_settings(self) -> DesktopAISettings:
        if self._settings_store is None:
            return DesktopAISettings()
        provider_id = str(self._settings_store.value("ai/provider", "deepseek"))
        try:
            defaults = default_provider_settings(provider_id)
        except ProviderConfigurationError:
            defaults = default_provider_settings("deepseek")
        return DesktopAISettings(
            enabled=False,
            provider_id=defaults.provider_id,
            base_url=str(
                self._settings_store.value("ai/base_url", defaults.base_url)
            ),
            model=str(
                self._settings_store.value("ai/model", defaults.model)
            ),
            api_key="",
        )

    def _persist_non_secret_settings(self) -> None:
        if self._settings_store is None:
            return
        self._settings_store.setValue("appearance/language", self.preferences.language)
        self._settings_store.setValue("appearance/theme", self.preferences.theme)
        self._settings_store.setValue("ai/provider", self.ai_settings.provider_id)
        self._settings_store.setValue("ai/base_url", self.ai_settings.base_url)
        self._settings_store.setValue("ai/model", self.ai_settings.model)
        self._settings_store.sync()

    def _resolved_theme(self) -> str:
        if self.preferences.theme != "system":
            return self.preferences.theme
        app = QApplication.instance()
        if app is not None:
            try:
                if app.styleHints().colorScheme() == Qt.ColorScheme.Dark:
                    return "dark"
            except AttributeError:
                pass
        return "light"

    def apply_theme(self) -> None:
        resolved = self._resolved_theme()
        self.setStyleSheet(stylesheet(resolved))
        self.ai_toggle.setTheme(resolved)

    def retranslate_ui(self) -> None:
        language = self.preferences.language
        self.setWindowTitle(
            text(
                language,
                "window_title",
                app=APP_NAME,
                version=DISPLAY_VERSION,
            )
        )
        self.brand.setText(f"{APP_NAME}  ·  {DISPLAY_VERSION}")
        self.product_descriptor.setText(text(language, "product_descriptor"))
        self.ai_toggle.setAccessibleName(text(language, "ai_toggle"))
        self._update_ai_toggle_label()
        self.settings_button.setText(text(language, "settings"))
        self.step_labels[0].setText(text(language, "step_select"))
        self.step_labels[1].setText(text(language, "step_analyse"))
        self.step_labels[2].setText(text(language, "step_review"))
        self.progress_label.setText(text(language, "analysing"))
        self.file_page.set_language(language)
        self.report_page.set_language(language)

    def _set_step(self, active_index: int) -> None:
        for index, label in enumerate(self.step_labels):
            label.setProperty("active", index == active_index)
            label.style().unpolish(label)
            label.style().polish(label)

    @Slot(int)
    def _stack_changed(self, index: int) -> None:
        if self.progress_panel.isVisible():
            self._set_step(1)
        else:
            self._set_step(2 if index == 1 else 0)

    @Slot(bool)
    def _on_ai_toggled(self, checked: bool) -> None:
        self.ai_settings.enabled = checked
        self._update_ai_toggle_label()

    def _update_ai_toggle_label(self) -> None:
        enabled = self.ai_toggle.isChecked()
        key = "ai_state_on" if enabled else "ai_state_off"
        self.ai_toggle_label.setText(text(self.preferences.language, key))
        self.ai_toggle_label.setProperty("enabledState", enabled)
        self.ai_toggle_label.style().unpolish(self.ai_toggle_label)
        self.ai_toggle_label.style().polish(self.ai_toggle_label)

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
        dialog = AISettingsDialog(
            self.ai_settings, self, preferences=self.preferences
        )
        dialog.setStyleSheet(stylesheet(self._resolved_theme()))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.ai_settings = dialog.settings()
            self.preferences = dialog.preferences()
            with QSignalBlocker(self.ai_toggle):
                self.ai_toggle.setChecked(self.ai_settings.enabled)
            self._persist_non_secret_settings()
            self.retranslate_ui()
            self.apply_theme()

    def _new_run_dir(self) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return self.report_root / f"report-{stamp}-{uuid.uuid4().hex[:8]}"

    @Slot()
    def start_analysis(self) -> None:
        language = self.preferences.language
        if self.thread is not None and self.thread.isRunning():
            QMessageBox.information(
                self,
                text(language, "analysis_running"),
                text(language, "analysis_running_body"),
            )
            return
        source = self.file_page.source_zone.path
        revised = self.file_page.revised_zone.path
        if source is None or revised is None:
            QMessageBox.warning(
                self,
                text(language, "missing_files"),
                text(language, "missing_files_body"),
            )
            return
        if source.resolve() == revised.resolve():
            QMessageBox.warning(
                self,
                text(language, "same_file"),
                text(language, "same_file_body"),
            )
            return
        if self.ai_settings.enabled and not self.ai_settings.api_key.strip():
            QMessageBox.warning(
                self,
                text(language, "missing_key"),
                text(language, "missing_key_body"),
            )
            return
        self.file_page.set_busy(True)
        self.settings_button.setEnabled(False)
        self.ai_toggle.setEnabled(False)
        self.brand_mark.setBusy(True)
        self.progress_panel.show()
        self._set_step(1)
        output_dir = self._new_run_dir()
        self.thread = QThread(self)
        self.worker = AnalysisWorker(
            source,
            revised,
            output_dir,
            DesktopAISettings(**vars(self.ai_settings)),
            language,
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
        self.brand_mark.playCompletion()
        self._set_step(2)
        if explanation is not None and explanation.get("status") == "ERROR":
            reason = str(explanation.get("error", text(
                self.preferences.language, "ai_failed_body"
            )))
            QMessageBox.warning(
                self,
                text(self.preferences.language, "ai_failed"),
                text(self.preferences.language, "ai_failed_reason", reason=reason),
            )

    @Slot(str)
    def _analysis_failed(self, message: str) -> None:
        self.progress_panel.hide()
        self.brand_mark.setBusy(False)
        self.file_page.set_busy(False)
        self.settings_button.setEnabled(True)
        self.ai_toggle.setEnabled(True)
        self._set_step(0)
        QMessageBox.critical(
            self, text(self.preferences.language, "analysis_failed"), message
        )

    @Slot()
    def _thread_finished(self) -> None:
        if self.progress_panel.isVisible():
            self.brand_mark.setBusy(False)
        self.file_page.set_busy(False)
        self.settings_button.setEnabled(True)
        self.ai_toggle.setEnabled(True)
        self.thread = None
        self.worker = None

    @Slot()
    def show_file_page(self) -> None:
        self.stack.setCurrentWidget(self.file_page)
        self._set_step(0)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.thread is not None and self.thread.isRunning():
            QMessageBox.information(
                self,
                text(self.preferences.language, "analysis_running"),
                text(self.preferences.language, "close_running"),
            )
            event.ignore()
            return
        super().closeEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if sys.platform != "win32":
            return
        try:
            import ctypes

            preference = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                int(self.winId()), 33, ctypes.byref(preference), ctypes.sizeof(preference)
            )
        except (AttributeError, OSError):
            pass


APP_STYLESHEET = stylesheet("light")


def main() -> int:
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "BIMChangeAgent.Desktop"
            )
        except (AttributeError, OSError):
            pass
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("BIMChange-Agent")
    if APP_ICON_PATH.is_file():
        app.setWindowIcon(QIcon(str(APP_ICON_PATH)))
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
            error if isinstance(error, Exception) else RuntimeError(str(error_type)),
            window.preferences.language,
        )
        QMessageBox.critical(
            window,
            text(window.preferences.language, "unexpected_title"),
            message,
        )

    sys.excepthook = show_unhandled_error
    if "--no-splash" in sys.argv:
        window.show()
    else:
        splash = BrandSplash()
        splash.finished.connect(window.show)
        splash.show()
        splash.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
