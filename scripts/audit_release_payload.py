"""Hash the exact staged portable payload and verify native provenance.

Does not publish, modify the package or assert installer acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from audit_qt_bundle import audit as audit_qt


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def audit(package, output, archive=None):
    package=package.resolve()
    if output.exists():
        raise FileExistsError(output)
    if not (package/'BIMChange-Agent.exe').is_file():
        raise ValueError('Missing executable')
    if list(package.glob('*NOT-FOR-DISTRIBUTION*')):
        raise ValueError('Private validation payload cannot be treated as release candidate')
    qt=audit_qt(package)
    proofs=list((package/'licenses/python-package-metadata').glob('ifcopenshell-*/NO-CGAL-BUILD.json'))
    if len(proofs)!=1:
        raise ValueError('Missing unique no-CGAL build proof')
    proof=json.loads(proofs[0].read_text())
    if proof.get('status')!='PASS' or set(proof.get('disabled_kernels',{}))!={'cgal','cgal-simple'}:
        raise ValueError('Native kernel gate not satisfied')
    patch = proofs[0].with_name('ifc-swig.patch')
    if not patch.is_file() or sha(patch) != proof.get('upstream_build_patch', {}).get('patch_sha256'):
        raise ValueError('Missing or changed upstream interface patch')
    for entry in proof['native_files']:
        actual=package/'_internal/ifcopenshell'/entry['name']
        if not actual.is_file() or sha(actual)!=entry['sha256']:
            raise ValueError(f'Native DLL changed or missing: {entry["name"]}')
    for file in package.rglob('*.ifc'):
        if file.parent!=package/'_internal/ifcopenshell/util/schema' or not file.name.startswith('Pset_'):
            raise ValueError('Unexpected IFC in package')
    if list(package.rglob('*.glb')) or list(package.rglob('.env')):
        raise ValueError('Unexpected model/credential file in package')
    inventory=json.loads((package/'licenses/source-inventory.json').read_text())
    if sha(package/'licenses/UPSTREAM-NOTICES.zip')!=inventory['notice_zip_sha256']:
        raise ValueError('Notice archive mismatch')
    files=[{'path':p.relative_to(package).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size}
           for p in sorted(package.rglob('*')) if p.is_file()]
    if archive:
        with zipfile.ZipFile(archive) as zipped:
            names={info.filename for info in zipped.infolist() if not info.is_dir()}
            expected={package.name+'/'+entry['path'] for entry in files}
            if names!=expected:
                raise ValueError('Portable ZIP file set differs from tested directory')
            for entry in files:
                with zipped.open(package.name+'/'+entry['path']) as stream:
                    if hashlib.file_digest(stream,'sha256').hexdigest()!=entry['sha256']:
                        raise ValueError('Portable ZIP bytes differ from tested directory')
    result={'status':'PASS','scope':'staged-payload-integrity-not-publication',
            'version':'1.0.0','files':files,'qt_modules':qt['modules'],
            'native_proof_sha256':sha(proofs[0]),'upstream_notice_count':inventory['notice_files'],
            'source_archive_count':len(inventory['archives'])}
    if archive:
        result['zip']={'name':archive.name,'sha256':sha(archive),'bytes':archive.stat().st_size}
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in result.items() if key not in {'files','qt_modules'}}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--zip',type=Path)
    args=parser.parse_args()
    audit(args.package,args.output,args.zip)
