"""Save/restore disposable-runner IFC intermediates, with strict environment checks.

Unchanged input files regain their original timestamps only after SHA-256 checks;
changed inputs remain fresh so MSBuild dependency tracking rebuilds affected units.
The ordinary CMake build (never BuildProjectReferences=false) is still mandatory.
Archives must come from the same repository's authenticated Actions artifacts.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import zipfile


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def identity(root, repo):
    return {'format': 1, 'root': str(root), 'repo': str(repo),
            'image': os.environ.get('ImageVersion'), 'python': sys.version,
            'pins': digest(repo/'packaging/native-sources.json'),
            'recipe': digest(repo/'scripts/build_ifcopenshell_no_cgal.ps1')}


def inputs(root, repo):
    for label, directory in [('source', repo/'.native-sources/ifcopenshell'),
                             ('occt', root/'install/occt'), ('boost', root/'install/boost'),
                             ('eigen', root/'sources/eigen')]:
        for path in directory.rglob('*'):
            relative = path.relative_to(directory)
            if '.git' in relative.parts or path.is_symlink() or not path.is_file():
                continue
            yield label + '/' + relative.as_posix(), path


def safe_output(root, name):
    relative = PurePosixPath(name)
    if '\\' in name or ':' in name or relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Unsafe checkpoint path')
    if not relative.parts or relative.parts[0] not in ('ifc-build', 'install'):
        raise ValueError('Unexpected checkpoint root')
    if relative.parts[0] == 'install' and relative.parts[1:2] != ('ifc',):
        raise ValueError('Unexpected checkpoint install target')
    target = (root / relative).resolve()
    target.relative_to(root)
    return target


def save(root, repo, archive):
    if not (root/'ifc-build/CMakeCache.txt').is_file():
        print('No configured IFC build to checkpoint'); return
    metadata = {'identity': identity(root, repo), 'inputs': {}, 'outputs': {}}
    for name, path in inputs(root, repo):
        metadata['inputs'][name] = [digest(path), path.stat().st_mtime_ns]
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=1) as output:
        for directory in (root/'ifc-build', root/'install/ifc'):
            for path in directory.rglob('*'):
                if path.is_symlink():
                    raise ValueError('Symlink in native build output')
                if not path.is_file():
                    continue
                name = path.relative_to(root).as_posix()
                metadata['outputs'][name] = path.stat().st_mtime_ns
                output.write(path, name)
        output.writestr('checkpoint.json', json.dumps(metadata))
    print(json.dumps({'checkpoint': str(archive), 'bytes': archive.stat().st_size,
                      'files': len(metadata['outputs']), 'sha256': digest(archive)}))


def restore(root, repo, archive):
    with zipfile.ZipFile(archive) as source:
        metadata = json.loads(source.read('checkpoint.json'))
        if metadata['identity'] != identity(root, repo):
            raise ValueError('Checkpoint toolchain, paths, Python, pins or recipe mismatch')
        names = source.namelist()
        if len(names) != len(set(names)) or set(names) != set(metadata['outputs']) | {'checkpoint.json'}:
            raise ValueError('Checkpoint member manifest mismatch')
        targets = {name: safe_output(root, name) for name in metadata['outputs']}
        if any(path.exists() for path in targets.values()):
            raise ValueError('Refusing to overwrite an existing IFC build')
        # Verify all ZIP CRCs before restoring any files or touching input timestamps.
        if source.testzip() is not None:
            raise ValueError('Corrupt checkpoint')
        for name, path in targets.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with source.open(name) as src, path.open('xb') as dst:
                import shutil
                shutil.copyfileobj(src, dst, 1024*1024)
            timestamp = metadata['outputs'][name]
            os.utime(path, ns=(timestamp, timestamp))
    retained = changed = 0
    for name, path in inputs(root, repo):
        old = metadata['inputs'].get(name)
        if old and digest(path) == old[0]:
            os.utime(path, ns=(path.stat().st_atime_ns, old[1])); retained += 1
        else:
            changed += 1
    print(json.dumps({'restored_files': len(targets), 'unchanged_inputs': retained,
                      'changed_or_new_inputs': changed,
                      'note': 'Normal CMake/MSBuild dependency validation still required'}))


if __name__ == '__main__':
    operation, native, project, output = sys.argv[1:]
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_OS') != 'Windows':
        raise SystemExit('Disposable Windows CI only')
    root = Path(native).resolve()
    root.relative_to(Path(os.environ['RUNNER_TEMP']).resolve())
    if root == Path(os.environ['RUNNER_TEMP']).resolve():
        raise SystemExit('Native root must be below runner temporary directory')
    {'save': save, 'restore': restore}[operation](root, Path(project).resolve(), Path(output).resolve())
