"""Allowlisted ephemeral loopback server for the R4 WebEngine candidate."""

from __future__ import annotations

import secrets
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import quote


class _AllowlistedHandler(SimpleHTTPRequestHandler):
    server_version = "BIMChange-R4/0.1"

    def __init__(self, *args, directory: str, token: str, allowed: set[str], **kwargs):
        self._token = token
        self._allowed = allowed
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        self.server.request_paths.append(self.path)
        super().do_GET()

    def send_response(self, code: int, message: str | None = None) -> None:
        self.server.response_codes.append(code)
        super().send_response(code, message)

    def _relative_request(self) -> str | None:
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        prefix = f"/{self._token}/"
        if not path.startswith(prefix):
            return None
        relative = path[len(prefix) :]
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts:
            return None
        normalized = pure.as_posix()
        return normalized if normalized in self._allowed else None

    def translate_path(self, _path: str) -> str:
        relative = self._relative_request()
        if relative is None:
            return str(Path(self.directory) / "__blocked__")
        return str(Path(self.directory).joinpath(*PurePosixPath(relative).parts))

    def send_head(self):
        if self._relative_request() is None:
            self.send_error(404)
            return None
        return super().send_head()

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        super().end_headers()


class LocalViewerServer:
    def __init__(self, bundle: Path) -> None:
        self.bundle = bundle.expanduser().resolve()
        if not self.bundle.is_dir():
            raise FileNotFoundError(self.bundle)
        self.token = secrets.token_urlsafe(24)
        allowed = {
            path.relative_to(self.bundle).as_posix()
            for path in self.bundle.rglob("*")
            if path.is_file()
        }
        handler = partial(
            _AllowlistedHandler,
            directory=str(self.bundle),
            token=self.token,
            allowed=allowed,
        )
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._server.request_paths = []
        self._server.response_codes = []
        self._thread = threading.Thread(
            target=lambda: self._server.serve_forever(poll_interval=0.02),
            name="bimchange-r4-loopback",
            daemon=True,
        )
        self._started = False
        self._allowed = allowed

    def allow_directory(self, directory: Path) -> None:
        """Register only completed scene files inside this session's root."""
        directory = directory.resolve()
        directory.relative_to(self.bundle)
        additions = set()
        for path in directory.rglob("*"):
            if path.is_file():
                path.resolve().relative_to(self.bundle)
                additions.add(path.relative_to(self.bundle).as_posix())
        self._allowed.update(additions)

    @property
    def origin(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    @property
    def allowed_prefix(self) -> str:
        return f"{self.origin}/{self.token}/"

    @property
    def request_paths(self) -> list[str]:
        return list(self._server.request_paths)

    @property
    def response_codes(self) -> list[int]:
        return list(self._server.response_codes)

    def start(self) -> None:
        if not self._started:
            self._thread.start()
            self._started = True

    def url(self, relative_path: str) -> str:
        pure = PurePosixPath(relative_path)
        if pure.is_absolute() or ".." in pure.parts:
            raise ValueError("Viewer path must be bundle-relative")
        return self.allowed_prefix + "/".join(quote(part) for part in pure.parts)

    def close(self) -> None:
        if self._started:
            self._server.shutdown()
            self._thread.join(timeout=5)
            self._started = False
        self._server.server_close()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
