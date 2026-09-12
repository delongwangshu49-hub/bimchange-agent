"""Lazily imported Qt WebEngine runtime for the R4 candidate."""

from __future__ import annotations

from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
    QWebEngineUrlRequestInfo,
    QWebEngineUrlRequestInterceptor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView


class RequestInterceptor(QWebEngineUrlRequestInterceptor):
    def __init__(self, allowed_prefix: str, parent=None) -> None:
        super().__init__(parent)
        self.allowed_prefix = allowed_prefix
        self.blocked_requests = 0
        self.blocked_urls: list[str] = []

    def interceptRequest(self, info: QWebEngineUrlRequestInfo) -> None:  # noqa: N802
        if not info.requestUrl().toString().startswith(self.allowed_prefix):
            self.blocked_requests += 1
            self.blocked_urls.append(info.requestUrl().toString())
            info.block(True)


class RestrictedPage(QWebEnginePage):
    def __init__(self, profile, allowed_prefix: str, parent=None) -> None:
        super().__init__(profile, parent)
        self.allowed_prefix = allowed_prefix

    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):  # noqa: N802
        del navigation_type
        if not is_main_frame:
            return True
        return url.toString().startswith(self.allowed_prefix)

    def createWindow(self, _window_type):  # noqa: N802
        return None


__all__ = [
    "QWebEngineProfile",
    "QWebEngineSettings",
    "QWebEngineView",
    "RequestInterceptor",
    "RestrictedPage",
]
