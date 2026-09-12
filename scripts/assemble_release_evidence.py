"""Collect exact, already-tested public artifacts into a new release directory.

Does not set approval gates or publish. Private validation packages are rejected.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from verify_release import verify_evidence


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def assemble(args):
    roles = ('installer', 'portable', 'qt_sources', 'native_python_sources', 'notices',
             'payload_manifest', 'frozen_smoke', 'installer_acceptance', 'license_review', 'source_inventory')
    sources = {role: getattr(args, role).resolve(strict=True) for role in roles}
    if any('NOT-FOR-DISTRIBUTION' in str(path) for path in sources.values()):
        raise ValueError('Private validation artifacts cannot be published')
    if sources['installer'].name != 'BIMChange-Agent-1.0.0-win-x64-setup.exe' or sources['portable'].name != 'BIMChange-Agent-1.0.0-win-x64.zip':
        raise ValueError('Unexpected release identity')
    names = {'payload_manifest': 'payload-manifest.json', 'frozen_smoke': 'frozen-smoke.json',
             'installer_acceptance': 'installer-acceptance.json', 'license_review': 'license-review.json',
             'source_inventory': 'source-inventory.json'}
    args.output.mkdir(parents=True, exist_ok=False)
    entries = {}
    for role, source in sources.items():
        name = names.get(role, source.name)
        target = args.output / name
        if target.exists():
            raise ValueError('Duplicate output filename')
        shutil.copy2(source, target)
        digest = sha(source)
        if sha(target) != digest:
            raise ValueError('Copy mismatch')
        entries[role] = {'path': name, 'sha256': digest, 'bytes': target.stat().st_size}
    evidence = {'version': '1.0.0', 'status': 'STAGED_NOT_PUBLISHED', 'files': entries,
                'smoke_payload_manifest_sha256': entries['payload_manifest']['sha256']}
    (args.output / 'release-evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    count = verify_evidence(args.output)
    lines = [f"{entry['sha256']}  {entry['path']}" for entry in entries.values()]
    lines.append(f"{sha(args.output / 'release-evidence.json')}  release-evidence.json")
    (args.output / 'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    for role in ('installer', 'portable'):
        entry = entries[role]
        (args.output / (entry['path']+'.sha256.txt')).write_text(f"{entry['sha256']}  {entry['path']}\n", encoding='utf-8')
    print(json.dumps({'status': 'PASS', 'scope': 'evidence-integrity-not-publication', 'files_verified': count}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for role in ('installer', 'portable', 'qt_sources', 'native_python_sources', 'notices',
                 'payload_manifest', 'frozen_smoke', 'installer_acceptance', 'license_review', 'source_inventory'):
        parser.add_argument('--'+role.replace('_', '-'), type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    assemble(parser.parse_args())
