"""Bind the reviewed Windows runtime/source mapping to an exact payload manifest.

This is an engineering distribution-evidence check, not a legal certification.
Unknown binary families, absent source archives and changed payloads fail closed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


COMPONENTS = {
    'application': ('MIT; PyInstaller GPL bootloader exception', ['pyinstaller-6.22.0.tar.gz']),
    'python': ('PSF and incorporated third-party terms', ['Python-3.13.15.tar.xz']),
    'openssl': ('Apache-2.0', ['openssl-3.0.21.tar.gz']),
    'microsoft-runtime': ('Microsoft Distributable Code; Windows-only', ['Python-3.13.15.tar.xz']),
    'ifcopenshell': ('LGPL-3.0-or-later; CGAL disabled; Boost BSL-1.0; Eigen MPL-2.0',
                    ['ifcopenshell-1c5b825-source.tar.gz', 'boost-1.86.0-cmake.tar.xz', 'eigen-3.3.9-source.tar.gz']),
    'occt': ('LGPL-2.1 with OCCT additional exception', ['occt-7.8.1-source.tar.gz']),
    'qt': ('LGPL-3.0 option plus separately licensed bundled components',
           ['qtbase-everywhere-src-6.11.1.tar.xz','qtdeclarative-everywhere-src-6.11.1.tar.xz',
            'qtimageformats-everywhere-src-6.11.1.tar.xz','qtpositioning-everywhere-src-6.11.1.tar.xz',
            'qtsvg-everywhere-src-6.11.1.tar.xz','qtwebchannel-everywhere-src-6.11.1.tar.xz',
            'qttranslations-everywhere-src-6.11.1.tar.xz']),
    'qt-webengine-pdf': ('Qt LGPL-3.0 option; Chromium/PDFium/FFmpeg separate notices including LGPL-2.1',
                         ['qtwebengine-everywhere-src-6.11.1.tar.xz']),
    'pyside-shiboken': ('LGPL-3.0 option', ['pyside-setup-everywhere-src-6.11.1.tar.xz']),
    'mesa-llvm': ('Mesa/LLVM MIT/Boost and incorporated notices; see exact Qt licenses.qdoc',
                  ['qtdoc-everywhere-src-6.11.1.tar.xz']),
    'numpy': ('BSD and incorporated BLAS/LAPACK/compiler runtime notices and exceptions', ['numpy-2.5.1.tar.gz']),
    'shapely': ('BSD-3-Clause', ['shapely-2.1.2.tar.gz']),
    'geos': ('LGPL-2.1-or-later', ['geos-3.13.1.tar.bz2']),
    'cachebox': ('MIT; locked Rust crate notices retained', ['cachebox-5.2.3.tar.gz']),
    'rpds': ('MIT; locked Rust crate notices retained', ['rpds_py-2026.6.3.tar.gz']),
}
PYTHON_BINARIES = set(('python3.dll python313.dll libffi-8.dll sqlite3.dll _asyncio.pyd _bz2.pyd '
    '_ctypes.pyd _decimal.pyd _hashlib.pyd _lzma.pyd _multiprocessing.pyd _overlapped.pyd '
    '_queue.pyd _socket.pyd _sqlite3.pyd _ssl.pyd _uuid.pyd _wmi.pyd pyexpat.pyd select.pyd unicodedata.pyd').split())


def component(relative):
    path = Path(relative)
    name = path.name.lower()
    parts = [part.lower() for part in path.parts]
    if relative == 'BIMChange-Agent.exe': return 'application'
    if name.startswith(('msvcp140', 'vcruntime140', 'api-ms-win-')) or name == 'ucrtbase.dll': return 'microsoft-runtime'
    if len(parts) == 2 and name in ('libcrypto-3.dll', 'libssl-3.dll'): return 'openssl'
    if len(parts) == 2 and name in PYTHON_BINARIES: return 'python'
    if parts[1:2] == ['ifcopenshell']:
        if name.startswith('tk') and name.endswith('.dll'): return 'occt'
        if name == '_ifcopenshell_wrapper.cp313-win_amd64.pyd': return 'ifcopenshell'
    if parts[1:2] == ['pyside6']:
        if name == 'opengl32sw.dll': return 'mesa-llvm'
        if name.endswith('.pyd') or name in ('pyside6.abi3.dll','pyside6qml.abi3.dll'): return 'pyside-shiboken'
        if name.startswith(('qt6webengine','qt6pdf','qtwebengineprocess','qpdf.')): return 'qt-webengine-pdf'
        if name.startswith('qt6') or 'plugins' in parts: return 'qt'
    if parts[1:2] == ['shiboken6']: return 'pyside-shiboken'
    if parts[1:2] in (['numpy'], ['numpy.libs']): return 'numpy'
    if parts[1:2] == ['shapely']: return 'shapely'
    if parts[1:2] == ['shapely.libs'] and name.startswith('geos'): return 'geos'
    if parts[1:2] == ['cachebox']: return 'cachebox'
    if parts[1:2] == ['rpds']: return 'rpds'
    raise ValueError('Unreviewed binary family: '+relative)


def audit(package, manifest, sources, output):
    if output.exists(): raise FileExistsError(output)
    payload = json.loads(manifest.read_text())
    if payload['status'] != 'PASS': raise ValueError('Payload integrity not passed')
    inventory = json.loads((package/'licenses/source-inventory.json').read_text())
    archives = {entry['file']: entry for entry in inventory['archives']}
    for entry in archives.values():
        if sha(sources/entry['file']) != entry['sha256']: raise ValueError('Source changed: '+entry['file'])
    notices = package/'licenses/UPSTREAM-NOTICES.zip'
    if sha(notices) != inventory['notice_zip_sha256']: raise ValueError('Notices changed')
    with zipfile.ZipFile(notices) as zipped:
        names = zipped.namelist()
        for required in ('OCCT_LGPL_EXCEPTION.txt', 'licenses.qdoc', 'COPYING.LGPLv2.1', 'LGPL-3.0-only.txt'):
            if not any(name.endswith('/'+required) for name in names): raise ValueError('Missing original notice: '+required)
    binaries = []
    for entry in payload['files']:
        path = package/entry['path']
        if sha(path) != entry['sha256']: raise ValueError('Payload changed: '+entry['path'])
        if path.suffix.lower() in ('.exe','.dll','.pyd'):
            group = component(entry['path'])
            binaries.append({**entry, 'component': group})
    proofs = list((package/'licenses/python-package-metadata').glob('ifcopenshell-*/NO-CGAL-BUILD.json'))
    if len(proofs) != 1: raise ValueError('Missing native proof')
    proof = json.loads(proofs[0].read_text())
    if proof['status'] != 'PASS' or set(proof['disabled_kernels']) != {'cgal','cgal-simple'}:
        raise ValueError('Native disabled-kernel evidence missing')
    if sha(proofs[0].with_name('ifc-swig.patch')) != proof['upstream_build_patch']['patch_sha256']:
        raise ValueError('Native corresponding-source patch changed')
    groups = {name: {'license_basis': terms, 'source_archives': files,
                    'binary_count': sum(entry['component']==name for entry in binaries)}
              for name, (terms, files) in COMPONENTS.items()}
    for group in groups.values():
        if not set(group['source_archives']) <= set(archives): raise ValueError('Source mapping incomplete')
    distributions = sorted(path.name for path in (package/'licenses/python-package-metadata').iterdir() if path.is_dir())
    for distribution in distributions:
        if not (package/'licenses/python-package-metadata'/distribution/'METADATA').is_file():
            raise ValueError('Package license metadata absent')
    for name in ('LICENSE','THIRD-PARTY-NOTICES.txt','CORRESPONDING-SOURCE.txt','licenses/PYTHON-LICENSE.txt',
                 'licenses/THREE-MIT.txt','licenses/LGPL-3.0.txt','licenses/GPL-3.0.txt','licenses/INNO-SETUP.txt'):
        if not (package/name).is_file(): raise ValueError('Missing distribution notice: '+name)
    result = {'status': 'PASS', 'scope': 'exact-runtime-distribution-evidence-not-legal-certification',
              'payload_manifest_sha256': sha(manifest), 'components': groups, 'binary_files': binaries,
              'python_metadata_directories': distributions, 'source_archives_verified': len(archives),
              'original_notice_files': inventory['notice_files'], 'project_license': 'MIT',
              'native_runtime_version_string': proof['version'], 'native_wheel_version': proof['wheel_version'],
              'native_version_note': 'Legacy upstream runtime string is 0.8.0; provenance is pinned source commit, patch and wheel digests, not this string.',
              'replacement_instructions': 'CORRESPONDING-SOURCE.txt',
              'review_basis': 'Exact supplied source notices, installed metadata, DLL inventory, native import proof, source digests and documented replaceable-library build route; unused source notices do not imply binary inclusion.',
              'installer_notice': 'Original Inno Setup notices retained; the compiler itself is not included.'}
    output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'status':'PASS','binary_files':len(binaries),'sources':len(archives),'notices':inventory['notice_files']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('package','manifest','sources','output'): parser.add_argument(name, type=Path)
    args = parser.parse_args()
    audit(args.package, args.manifest, args.sources, args.output)
