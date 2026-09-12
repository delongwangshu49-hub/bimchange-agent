"""Minimal LGPL upstream-interface build patch; original native algorithms unchanged.

OpaqueCoordinate is kernel-independent, but its SWIG instantiations were inside
IFOPSH_WITH_CGAL. Move them after the common declaration, preserving CGAL=OFF.
Record the exact source diff with the build and include it in the resulting wheel.
"""
import difflib
import hashlib
import json
from pathlib import Path
import sys

ORIGINAL = 'c8d89f962a9429394f85b78ac7817bc83dae5e04e66eba7753ae7fc5bdce60aa'
DECLARATIONS = ('%template(OpaqueCoordinate_3) IfcGeom::OpaqueCoordinate<3>;\n'
                '%template(OpaqueCoordinate_4) IfcGeom::OpaqueCoordinate<4>;\n')
ANCHOR = '%include "../ifcgeom/ConversionResult.h"\n'


def patched(text):
    if hashlib.sha256(text.encode()).hexdigest() != ORIGINAL:
        raise ValueError('Unexpected upstream SWIG interface; refusing an unreviewed patch')
    if text.count(DECLARATIONS) != 1 or text.count(ANCHOR) != 1:
        raise ValueError('Unexpected SWIG declaration layout')
    return text.replace(DECLARATIONS, '', 1).replace(ANCHOR, ANCHOR + DECLARATIONS, 1)


def apply(source, evidence):
    target = Path(source)/'src/ifcwrap/IfcGeomWrapper.i'
    evidence = Path(evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    original = target.read_text(encoding='utf-8')
    result = patched(original)
    diff = ''.join(difflib.unified_diff(original.splitlines(True), result.splitlines(True),
                   fromfile='a/src/ifcwrap/IfcGeomWrapper.i', tofile='b/src/ifcwrap/IfcGeomWrapper.i'))
    target.write_text(result, encoding='utf-8', newline='\n')
    (evidence/'ifc-swig.patch').write_text(diff, encoding='utf-8', newline='\n')
    receipt = {'base_commit': '1c5b825d8ef05ab9d14a15dac12e9eae2f5a37c2',
               'original_lf_sha256': ORIGINAL,
               'patched_lf_sha256': hashlib.sha256(result.encode()).hexdigest(),
               'patch_sha256': hashlib.sha256(diff.encode()).hexdigest(),
               'change': 'Move kernel-independent OpaqueCoordinate SWIG instantiations outside CGAL guard',
               'upstream_license': 'LGPL-3.0-or-later'}
    (evidence/'ifc-swig-patch.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt))


if __name__ == '__main__':
    apply(*sys.argv[1:])
