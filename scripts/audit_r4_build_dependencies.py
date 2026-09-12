"""Reject host-tool DLL leakage into this generated private build."""
import ast
import json
import os
import sys
from pathlib import Path


def entries(value):
    if isinstance(value, (list, tuple)):
        if len(value) == 3 and value[-1] == "BINARY" and isinstance(value[0], str):
            yield value
        else:
            for child in value:
                yield from entries(child)


def audit(toc, application):
    application = application.resolve()
    if not (application / "BIMChange-Agent.exe").is_file():
        raise ValueError("Expected generated application executable")
    known_optional = {"libssl-3-x64.dll", "libcrypto-3-x64.dll"}
    known_system = {"icuuc.dll", "icudt78.dll"}
    removed = []
    for destination, origin, _ in entries(ast.literal_eval(toc.read_text(encoding="utf-8"))):
        if "/codex-primary-runtime/dependencies/native/poppler/library/bin/" not in origin.replace("\\", "/").lower():
            continue
        name = Path(destination).name.lower()
        if name not in known_optional | known_system:
            raise ValueError(f"Unexpected host-tool DLL; review required: {name}")
        if name in known_system and not (Path(os.environ["SystemRoot"]) / "System32/icuuc.dll").is_file():
            raise ValueError("Windows system ICU is required; do not substitute Poppler ICU")
        target = (application / "_internal" / destination).resolve()
        target.relative_to(application / "_internal")
        target.unlink(missing_ok=True)
        removed.append(destination)
    return {"host_tool_dlls_removed_from_generated_build": removed,
            "system_files_modified": False, "native_smoke_still_required": True}


if __name__ == "__main__":
    print(json.dumps(audit(Path(sys.argv[1]), Path(sys.argv[2])), indent=2))
