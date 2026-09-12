"""Create non-overwriting public source ZIPs from the reviewed archive inventory."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def bundle(source, inventory_path, output):
    output.mkdir(parents=True,exist_ok=False)
    inventory=json.loads(inventory_path.read_text())
    groups={'Qt-PySide':[],'native-python':[]}
    for entry in inventory['archives']:
        path=source/entry['file']
        if path.parent.resolve()!=source.resolve() or sha(path)!=entry['sha256']:
            raise ValueError('Source archive integrity check failed')
        key='Qt-PySide' if entry['file'].startswith(('qt','pyside-')) else 'native-python'
        groups[key].append(entry)
    results=[]
    for group,entries in groups.items():
        name=f'BIMChange-Agent-1.0.0-{group}-sources.zip'
        target=output/name
        with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_STORED) as archive:
            for entry in entries:
                archive.write(source/entry['file'],entry['file'])
            archive.writestr('SOURCE-INVENTORY.json',json.dumps(entries,indent=2))
        if target.stat().st_size>=2*1024**3:
            raise ValueError('Source asset exceeds GitHub per-file limit')
        results.append({'name':name,'sha256':sha(target),'bytes':target.stat().st_size,'archives':len(entries)})
    (output/'source-assets.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('inventory',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    bundle(args.source,args.inventory,args.output)
