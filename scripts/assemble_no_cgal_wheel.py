"""Assemble a privately validated wheel from a same-revision no-CGAL CI build.

The stock wheel supplies unchanged Python code/data and upstream notices; both
SWIG wrapper files are replaced together. Only recursively imported OCCT DLLs
are copied. All mutation targets are new directories below the CI build root.
"""
import base64
import csv
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pefile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assemble(root):
    root = Path(root).resolve()
    root.relative_to(Path(os.environ["RUNNER_TEMP"]).resolve())
    staging = root / "wheel-stage"
    staging.mkdir(exist_ok=False)
    stock = importlib.metadata.distribution("ifcopenshell")
    if stock.version != "0.8.5":
        raise RuntimeError("Expected unmodified upstream 0.8.5 Python payload")
    package = staging / "ifcopenshell"
    shutil.copytree(stock.locate_file("ifcopenshell"), package,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for old in package.glob("_ifcopenshell_wrapper*.pyd"):
        old.resolve().relative_to(staging)
        old.unlink()
    installed = root / "install/ifc/ifcopenshell"
    binaries = list(installed.glob("_ifcopenshell_wrapper*.pyd"))
    if len(binaries) != 1:
        raise RuntimeError("Expected exactly one rebuilt extension")
    for source in [binaries[0], installed / "ifcopenshell_wrapper.py"]:
        shutil.copy2(source, package / source.name)
    libraries = {p.name.lower(): p for p in (root / "install/occt").rglob("*.dll")}
    pending = [package / binaries[0].name]
    copied = set()
    imports = {}
    while pending:
        target = pending.pop()
        with pefile.PE(str(target), fast_load=True) as pe:
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
            dependencies = [entry.dll.decode("ascii") for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])]
        imports[target.name] = dependencies
        for dependency in dependencies:
            key = dependency.lower()
            if key in libraries and key not in copied:
                copied.add(key)
                destination = package / libraries[key].name
                shutil.copy2(libraries[key], destination)
                pending.append(destination)
            elif key.startswith("tk") and key.endswith(".dll") and key not in libraries:
                raise RuntimeError(f"Unresolved OCCT dependency: {dependency}")
            if any(part in key for part in ("cgal", "mpfr", "mpir", "svgfill")):
                raise RuntimeError(f"Prohibited native dependency: {dependency}")
    cache = (root / "ifc-build/CMakeCache.txt").read_text()
    if "WITH_CGAL:BOOL=OFF" not in cache or "BUILD_ONLY_COMMON_SCHEMAS:BOOL=OFF" not in cache:
        raise RuntimeError("Build did not retain required configuration")
    version = "0.8.5+nocgal.1"
    metadata = staging / f"ifcopenshell-{version}.dist-info"
    old_metadata = stock.locate_file("ifcopenshell-0.8.5.dist-info")
    shutil.copytree(old_metadata, metadata)
    text = (metadata / "METADATA").read_text(encoding="utf-8")
    text = text.replace("Version: 0.8.5\n", f"Version: {version}\n", 1)
    (metadata / "METADATA").write_text(text, encoding="utf-8")
    (metadata / "WHEEL").write_text("Wheel-Version: 1.0\nGenerator: BIMChange no-CGAL build\nRoot-Is-Purelib: false\nTag: cp313-cp313-win_amd64\n", encoding="utf-8")
    for name in ("RECORD", "INSTALLER", "direct_url.json", "REQUESTED"):
        (metadata / name).unlink(missing_ok=True)
    # Native loading is tested in a clean process using the staged package.
    check = r'''
import json, ifcopenshell, ifcopenshell.geom, ifcopenshell.api
w = ifcopenshell.ifcopenshell_wrapper
expected = {'HEADER_SECTION_SCHEMA','IFC2X3','IFC4','IFC4X1','IFC4X2','IFC4X3','IFC4X3_ADD1','IFC4X3_ADD2','IFC4X3_TC1'}
assert set(w.schema_names()) == expected, w.schema_names()
model = ifcopenshell.api.run('project.create_file', version='IFC4')
ifcopenshell.api.run('root.create_entity', model, ifc_class='IfcProject')
ifcopenshell.api.run('unit.assign_unit', model)
context = ifcopenshell.api.run('context.add_context', model, context_type='Model')
body = ifcopenshell.api.run('context.add_context', model, context_type='Model', context_identifier='Body', target_view='MODEL_VIEW', parent=context)
wall = ifcopenshell.api.run('root.create_entity', model, ifc_class='IfcWall')
representation = ifcopenshell.api.run('geometry.add_wall_representation', model, context=body, length=2, height=3, thickness=.2)
ifcopenshell.api.run('geometry.assign_representation', model, product=wall, representation=representation)
shape = ifcopenshell.geom.create_shape(ifcopenshell.geom.settings(), wall, geometry_library='opencascade')
assert len(shape.geometry.faces) > 0
rejected = {}
for kernel in ('cgal', 'cgal-simple'):
    try:
        ifcopenshell.geom.create_shape(ifcopenshell.geom.settings(), wall, geometry_library=kernel)
    except RuntimeError as error:
        assert 'kernel' in str(error).lower() or 'cgal' in str(error).lower(), str(error)
        rejected[kernel] = str(error)
    else:
        raise AssertionError('CGAL still operational: '+kernel)
print(json.dumps({'status':'PASS','version':w.version(),'schemas':sorted(expected),'opencascade_triangles':len(shape.geometry.faces)//3,'disabled_kernels':rejected}))
'''
    environment = dict(os.environ, PYTHONPATH=str(staging))
    result = subprocess.run([sys.executable, "-c", check], env=environment, cwd=root,
                            capture_output=True, text=True)
    print(result.stdout)
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        result.check_returncode()
    proof = json.loads(result.stdout.strip().splitlines()[-1])
    proof.update({"wheel_version": version, "ifcopenshell_commit": "1c5b825d8ef05ab9d14a15dac12e9eae2f5a37c2",
                  "occt_commit": "bd2a789f15235755ce4d1a3b07379a2e062fdc2e", "native_imports": imports,
                  "native_files": [{"name": p.name, "sha256": digest(p)} for p in sorted(package.glob("*.dll"))]})
    proof["native_files"].append({"name": binaries[0].name, "sha256": digest(package / binaries[0].name)})
    patch = root / 'evidence/ifc-swig.patch'
    patch_receipt = json.loads((root / 'evidence/ifc-swig-patch.json').read_text())
    if digest(patch) != patch_receipt['patch_sha256']:
        raise RuntimeError('Upstream interface patch digest mismatch')
    proof['upstream_build_patch'] = patch_receipt
    shutil.copy2(patch, metadata / 'ifc-swig.patch')
    (metadata / "NO-CGAL-BUILD.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
    (root / "evidence/native-proof.json").write_text(json.dumps(proof, indent=2), encoding="utf-8")
    record = io.StringIO(newline="")
    writer = csv.writer(record, lineterminator="\n")
    for path in sorted(staging.rglob("*")):
        if path.is_file():
            encoded = base64.urlsafe_b64encode(bytes.fromhex(digest(path))).decode().rstrip("=")
            writer.writerow([path.relative_to(staging).as_posix(), f"sha256={encoded}", path.stat().st_size])
    writer.writerow([f"{metadata.name}/RECORD", "", ""])
    (metadata / "RECORD").write_text(record.getvalue(), encoding="utf-8", newline="")
    wheels = root / "wheels"
    wheels.mkdir(exist_ok=False)
    output = wheels / f"ifcopenshell-{version}-cp313-cp313-win_amd64.whl"
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(staging))
    print(json.dumps({"wheel": output.name, "sha256": digest(output), "bytes": output.stat().st_size}))


if __name__ == "__main__":
    assemble(sys.argv[1])
