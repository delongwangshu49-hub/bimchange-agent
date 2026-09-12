"""Preserve upstream notice files from the exact source archives, without executing them.

This deliberately includes notices for unlinked source-tree components as well;
the binary inventory determines what is actually shipped. It is not a substitute
for license review. Path traversal, links and duplicate paths are not extracted.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import zipfile


NOTICE = re.compile(r"^(licen[cs]es?|copying|copyright|notices?|authors|credits)([._-].*)?$", re.I)


def selected(path):
    return (bool(NOTICE.match(path.name)) or path.name == "qt_attribution.json"
            or path.name == "OCCT_LGPL_EXCEPTION.txt"
            or path.name == "README.chromium" or path.name.lower().endswith(".spdx")
            or any(part.lower() in {"licenses", "licences"} for part in path.parts))


def sha_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def collect(sources, output):
    output.mkdir(parents=True, exist_ok=False)
    archives = sorted(p for p in sources.iterdir() if p.name.endswith((".tar.xz", ".tar.gz", ".tar.bz2", ".tar", ".crate")))
    manifest = []
    records = []
    names = set()
    with zipfile.ZipFile(output / "UPSTREAM-NOTICES.zip", "x", zipfile.ZIP_DEFLATED) as notices:
        for archive in archives:
            digest = sha_file(archive)
            count = 0
            with tarfile.open(archive, "r|*") as source:
                for entry in source:
                    path = PurePosixPath(entry.name)
                    if path.is_absolute() or ".." in path.parts:
                        raise ValueError(f"Unsafe source member: {entry.name}")
                    if not entry.isfile() or not selected(path):
                        continue
                    if entry.size > 32 * 1024 * 1024:
                        raise ValueError(f"Unexpectedly large notice: {entry.name}")
                    data = source.extractfile(entry).read()
                    name = f"{archive.name}/{path.as_posix()}"
                    if name in names:
                        raise ValueError(f"Duplicate notice: {name}")
                    names.add(name)
                    notices.writestr(name, data)
                    records.append({"archive": archive.name, "path": path.as_posix(),
                                    "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
                    count += 1
            if not count:
                raise ValueError(f"No notices found in {archive.name}")
            manifest.append({"file": archive.name, "sha256": digest,
                             "bytes": archive.stat().st_size, "notice_files": count})
            print(json.dumps(manifest[-1]), flush=True)
        notices.writestr("NOTICE-INDEX.json", json.dumps(records, indent=2))
    report = {"status": "COLLECTED_REVIEW_REQUIRED", "notice_files": len(records),
              "archives": manifest, "notice_zip_sha256": sha_file(output / "UPSTREAM-NOTICES.zip"),
              "scope": "All matching upstream source notices, including unlinked components; not a binary license certificate."}
    (output / "source-inventory.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"notice_files": len(records), "notice_zip_sha256": report["notice_zip_sha256"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    collect(args.sources, args.output)
