"""Complete a selective Boost library install with unchanged upstream headers.

IfcOpenShell's CMake requests compiled Boost libraries, but also includes
header-only modules outside those libraries' dependency closure.
"""
import argparse
import json
from pathlib import Path
import re
import shutil


def complete_headers(source: Path, include: Path, ifc_source: Path):
    roots = sorted(set(source.glob("libs/*/include/boost")) |
                   set(source.glob("libs/numeric/*/include/boost")))
    if not roots:
        raise ValueError("No modular Boost headers found")
    headers = {}
    for root in roots:
        for file in sorted(root.rglob("*")):
            if not file.is_file():
                continue
            relative = Path("boost") / file.relative_to(root)
            if relative in headers and file.read_bytes() != headers[relative].read_bytes():
                raise ValueError(f"Conflicting upstream header: {relative}")
            headers[relative] = file
    required = {"boost/logic/tribool.hpp", "boost/uuid/uuid.hpp"}
    pattern = re.compile(r'^\s*#\s*include\s*[<"](boost/[^>"\s]+)[>"]', re.MULTILINE)
    for folder in ("ifcparse", "ifcgeom", "ifcwrap", "serializers"):
        directory = ifc_source / "src" / folder
        if not directory.is_dir():
            raise ValueError(f"Missing IfcOpenShell source directory: {folder}")
        for file in directory.rglob("*"):
            if file.is_file() and file.suffix.lower() in {".h", ".hpp", ".cpp", ".cxx", ".i"}:
                required.update(pattern.findall(file.read_text(encoding="utf-8", errors="replace")))
    missing = sorted(name for name in required if Path(name) not in headers)
    if missing:
        raise ValueError(f"Required Boost headers absent in pinned source: {missing}")
    # Validate every collision before copying; never replace different bytes.
    for relative, file in headers.items():
        destination = include / relative
        if destination.exists() and destination.read_bytes() != file.read_bytes():
            raise ValueError(f"Installed header differs from source: {relative}")
    for relative, file in headers.items():
        destination = include / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(file, destination)
    for name in required:
        if (include / name).read_bytes() != headers[Path(name)].read_bytes():
            raise ValueError(f"Header verification failed: {name}")
    receipt = {"status": "PASS", "header_files": len(headers),
               "direct_ifc_headers": sorted(required), "modified_upstream_headers": 0}
    print(json.dumps(receipt), flush=True)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("include", type=Path)
    parser.add_argument("ifc_source", type=Path)
    args = parser.parse_args()
    complete_headers(args.source, args.include, args.ifc_source)
