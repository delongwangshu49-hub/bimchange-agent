"""Read-only checks for local 1.0.0 preparation; public mode fails closed."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bimchange_agent import __version__

LOGO_SHA256 = "f37b513d8519fafd82ac727ab11e13eae0d37db42f7231a9fe30c8dfd95e0ff5"
GATES = ("exact_binary_license_inventory_reviewed", "corresponding_source_materials_ready",
         "final_binary_smoke_passed", "isolated_install_upgrade_uninstall_passed",
         "public_upload_authorized")


def verify(public=False):
    failures = []
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    if __version__ != "1.0.0" or project["project"]["version"] != __version__:
        failures.append("Python/package version mismatch")
    if "PySide6-Addons==6.11.1" not in project["project"]["optional-dependencies"]["desktop"]:
        failures.append("Desktop install is missing WebEngine Addons")
    pe = (ROOT / "packaging/windows/BIMChange-Agent.version-info.txt").read_text()
    if "filevers=(1, 0, 0, 0)" not in pe or "StringStruct('ProductVersion', '1.0.0')" not in pe:
        failures.append("PE version mismatch")
    iss = (ROOT / "packaging/windows/BIMChange-Agent.iss").read_text()
    if '#define AppVersion "1.0.0"' not in iss or '#define AppFileVersion "1.0.0.0"' not in iss:
        failures.append("Installer version mismatch")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for required in ("Experimental lineage / 实验沿革", "AI and privacy / AI 与隐私",
                     "https://github.com/delongwangshu49-hub/ifc-clashtrace",
                     "docs/assets/brand/bimchange-logo-evolution.gif"):
        if required not in readme:
            failures.append(f"Missing README content: {required}")
    links = re.findall(r'\]\(([^)]+)\)|src="([^"]+)"', readme)
    checked = []
    for pair in links:
        link = next(p for p in pair if p).split("#")[0]
        if not link or re.match(r"[a-z]+:", link):
            continue
        if not (ROOT / link).exists():
            failures.append(f"Missing README target: {link}")
        checked.append(link)
    logo = ROOT / "docs/assets/brand/bimchange-logo-evolution.gif"
    if hashlib.sha256(logo.read_bytes()).hexdigest() != LOGO_SHA256:
        failures.append("Original animated logo bytes changed")
    gates = json.loads((ROOT / "packaging/release-1.0.0-gates.json").read_text())
    pending = [key for key in GATES if gates.get(key) is not True]
    if public and pending:
        failures.extend(f"Public gate pending: {key}" for key in pending)
    return {"status": "FAIL" if failures else "PASS", "version": __version__,
            "scope": "public-release" if public else "local-source-document-check",
            "public_ready": not pending and not failures, "pending_public_gates": pending,
            "readme_local_targets_checked": len(checked), "logo_sha256": LOGO_SHA256,
            "failures": failures}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", action="store_true")
    result = verify(parser.parse_args().public)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
