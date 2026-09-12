"""Read-only checks for local 1.0.0 preparation; public mode fails closed."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bimchange_agent import __version__

LOGO_SHA256 = "f37b513d8519fafd82ac727ab11e13eae0d37db42f7231a9fe30c8dfd95e0ff5"
GATES = ("exact_binary_license_inventory_reviewed", "corresponding_source_materials_ready",
         "final_binary_smoke_passed", "isolated_install_upgrade_uninstall_passed",
         "public_upload_authorized")


def verify_evidence(directory):
    """Bind acceptance receipts to the exact assets about to be uploaded."""
    directory = Path(directory).resolve()
    manifest = json.loads((directory / 'release-evidence.json').read_text(encoding='utf-8'))
    required = {'installer', 'portable', 'qt_sources', 'native_python_sources',
                'notices', 'payload_manifest', 'frozen_smoke', 'installer_acceptance',
                'license_review', 'source_inventory'}
    entries = manifest['files']
    if not required <= set(entries) or manifest.get('version') != '1.0.0':
        raise ValueError('Incomplete release evidence')
    resolved = {}
    for role, entry in entries.items():
        path = (directory / entry['path']).resolve()
        path.relative_to(directory)
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != entry['sha256']:
            raise ValueError(f'Evidence digest mismatch: {role}')
        resolved[role] = path
    def read(role):
        return json.loads(resolved[role].read_text(encoding='utf-8-sig'))
    payload, installed, smoke, review = map(read, ('payload_manifest', 'installer_acceptance', 'frozen_smoke', 'license_review'))
    if any(item.get('status') != 'PASS' for item in (payload, installed, smoke, review)):
        raise ValueError('An acceptance receipt is not PASS')
    if payload['zip']['sha256'] != entries['portable']['sha256']:
        raise ValueError('Portable bytes do not match tested payload')
    if installed['installer_sha256'] != entries['installer']['sha256'] or installed['payload_manifest_sha256'] != entries['payload_manifest']['sha256']:
        raise ValueError('Installer acceptance belongs to different artifacts')
    if installed['payload_files_verified'] != len(payload['files']) or installed['upgrade_from'] != '0.9.0':
        raise ValueError('Incomplete installed-payload/upgrade verification')
    for key in ('fresh_install', 'desktop_startup', 'offline_comparison', 'preferences_preserved',
                'shortcut_target_and_icon', 'uninstall_executable_and_registry_removed', 'input_files_unchanged'):
        if installed.get(key) is not True:
            raise ValueError(f'Installer check missing: {key}')
    if smoke.get('frozen') is not True or smoke.get('errors') or smoke.get('session_removed') is not True:
        raise ValueError('Final frozen smoke did not pass')
    executables = [entry for entry in payload['files'] if entry['path'] == 'BIMChange-Agent.exe']
    if len(executables) != 1 or smoke.get('executable_sha256') != executables[0]['sha256']:
        raise ValueError('Frozen smoke executable does not match final payload')
    if manifest.get('smoke_payload_manifest_sha256') != entries['payload_manifest']['sha256']:
        raise ValueError('Frozen smoke is not bound to the staged payload')
    if review.get('payload_manifest_sha256') != entries['payload_manifest']['sha256']:
        raise ValueError('License review is not bound to the staged payload')
    inventory = read('source_inventory')
    if inventory['notice_zip_sha256'] != entries['notices']['sha256']:
        raise ValueError('Notices do not match corresponding-source inventory')
    source_entries = {entry['file']: entry for entry in inventory['archives']}
    supplied = set()
    for role in ('qt_sources', 'native_python_sources'):
        with zipfile.ZipFile(resolved[role]) as archive:
            for name in archive.namelist():
                if name == 'SOURCE-INVENTORY.json':
                    continue
                if name not in source_entries or name in supplied:
                    raise ValueError('Unexpected or repeated corresponding source')
                with archive.open(name) as stream:
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != source_entries[name]['sha256']:
                        raise ValueError('Corresponding source archive digest mismatch')
                supplied.add(name)
    if supplied != set(source_entries):
        raise ValueError('Missing corresponding source archives')
    return len(entries)


def verify(public=False, evidence=None):
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
    evidence_count = 0
    if public:
        if evidence is None:
            failures.append('Public release requires --evidence with hash-bound final artifacts')
        else:
            try:
                evidence_count = verify_evidence(evidence)
            except (OSError, ValueError, KeyError, TypeError) as error:
                failures.append(f'Public evidence failed: {error}')
    return {"status": "FAIL" if failures else "PASS", "version": __version__,
            "scope": "public-release" if public else "local-source-document-check",
            "public_ready": public and bool(evidence_count) and not pending and not failures,
            "evidence_files_verified": evidence_count, "pending_public_gates": pending,
            "readme_local_targets_checked": len(checked), "logo_sha256": LOGO_SHA256,
            "failures": failures}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", action="store_true")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    result = verify(args.public, args.evidence)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
