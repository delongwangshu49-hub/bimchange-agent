"""Private stdin/stdout worker: IFC parsing and tessellation stay outside Qt."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
import sys
import os
import uuid
from collections import OrderedDict
from pathlib import Path

from .r4_spatial_candidate import SpatialSessionCache, R4SpatialCandidateError, build_spatial_scene


def _restore_redirected_stdio() -> None:
    """Windowed frozen executables hide Python streams, even with QProcess pipes."""
    if os.name != "nt" or (sys.stdin is not None and sys.stdout is not None):
        return
    import ctypes
    import msvcrt
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel.GetStdHandle.restype = wintypes.HANDLE
    for name, handle_id, mode, flags in (("stdin", -10, "r", os.O_RDONLY),
                                        ("stdout", -11, "w", os.O_WRONLY)):
        if getattr(sys, name) is None:
            handle = kernel.GetStdHandle(handle_id & 0xFFFFFFFF)
            if not handle or handle == ctypes.c_void_p(-1).value:
                raise RuntimeError("Worker requires redirected local pipes")
            descriptor = msvcrt.open_osfhandle(handle, flags | os.O_BINARY)
            setattr(sys, name, os.fdopen(descriptor, mode, encoding="utf-8", buffering=1))


def main() -> int:
    _restore_redirected_stdio()
    cache = SpatialSessionCache()
    scenes: OrderedDict = OrderedDict()
    configuration = None
    for line in sys.stdin:
        request_id = None
        try:
            request = json.loads(line)
            request_id = request["id"]
            if configuration is None:
                configuration = request["inputs"]
            source = Path(configuration["source"])
            revised = Path(configuration["revised"])
            artifact = configuration["artifact"]
            root = Path(configuration["root"])
            change = request["change"]
            if change not in artifact.get("changes", []):
                raise R4SpatialCandidateError("change_not_in_report")
            cache.verify_inputs(source, revised, artifact)
            key = hashlib.sha256(json.dumps(change, sort_keys=True).encode()).hexdigest()
            hit = key in scenes
            if hit:
                scenes.move_to_end(key)
                result = scenes[key]
            else:
                records = (root / "records").resolve()
                output = records / (key + "-" + uuid.uuid4().hex)
                try:
                    with contextlib.redirect_stdout(io.StringIO()):
                        result = build_spatial_scene(
                            source_ifc=source, revised_ifc=revised, artifact=artifact,
                            change=change, output_directory=output,
                            cache=cache, include_viewer=False,
                        )
                except Exception:
                    # Only this attempt's newly named subdirectory can be removed.
                    if output.resolve().parent == records:
                        shutil.rmtree(output, ignore_errors=True)
                    raise
                scenes[key] = result
                while len(scenes) > 16:
                    _, expired = scenes.popitem(last=False)
                    shutil.rmtree(expired.bundle)
            reply = {"id": request_id, "ok": True, "manifest": str(result.manifest),
                     "target": result.target_global_id, "role": result.selected_ifc_role,
                     "context_count": result.context_count, "cache_hit": hit}
        except R4SpatialCandidateError as error:
            reply = {"id": request_id, "ok": False, "error": str(error)}
        except Exception:
            reply = {"id": request_id, "ok": False, "error": "scene_build_failed"}
        print(json.dumps(reply), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
