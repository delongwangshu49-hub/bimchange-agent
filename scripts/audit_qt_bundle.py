"""Read-only Qt module minimization gate, not a license-compliance certificate."""
import hashlib
import json
import sys
from pathlib import Path

EXPECTED_QT_MODULES = {
    "Core", "Gui", "Network", "OpenGL", "Pdf", "Positioning", "PrintSupport",
    "Qml", "QmlMeta", "QmlModels", "QmlWorkerScript", "Quick", "QuickWidgets",
    "Svg", "Test", "WebChannel", "WebEngineCore", "WebEngineWidgets", "Widgets",
}
FORBIDDEN_PLUGIN_DIRS = {"qmltooling", "platforminputcontexts", "generic", "position"}


def audit(application):
    root = Path(application) / "_internal" / "PySide6"
    dlls = sorted(root.glob("Qt6*.dll"))
    observed = {path.stem[3:] for path in dlls}
    if observed != EXPECTED_QT_MODULES:
        raise ValueError(f"Qt module set changed: extra={sorted(observed - EXPECTED_QT_MODULES)}, "
                         f"missing={sorted(EXPECTED_QT_MODULES - observed)}")
    for folder in FORBIDDEN_PLUGIN_DIRS:
        if list((root / "plugins" / folder).rglob("*.dll")):
            raise ValueError(f"Unused plugin family was collected: {folder}")
    if list((root / "qml").rglob("*.qml")):
        raise ValueError("The application does not use a QML import catalog")
    return {"status": "PASS", "scope": "qt-module-minimization-only",
            "public_license_gate_satisfied": False,
            "modules": [{"file": p.name, "bytes": p.stat().st_size,
                         "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in dlls]}


if __name__ == "__main__":
    print(json.dumps(audit(sys.argv[1]), indent=2))
