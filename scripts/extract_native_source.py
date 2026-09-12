"""Extract pinned native source archives with bounded paths and visible progress."""
import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import time


def extract(archive: Path, destination: Path):
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    started = reported = time.monotonic()
    count = size = 0
    archive_root = None
    with tarfile.open(archive, mode="r|*") as source:
        for member in source:
            name = PurePosixPath(member.name)
            if (name.is_absolute() or ".." in name.parts or
                    "\\" in member.name or ":" in member.name):
                raise ValueError(f"Unsafe archive entry: {member.name}")
            if not name.parts:
                continue
            if archive_root is None:
                archive_root = name.parts[0]
            if name.parts[0] != archive_root:
                raise ValueError("Expected one source archive root")
            relative = Path(*name.parts[1:])
            target = (destination / relative).resolve()
            target.relative_to(destination)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(member) as incoming, target.open("xb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing, 1024 * 1024)
                count += 1
                size += member.size
            else:
                raise ValueError(f"Unsupported link/device entry: {member.name}")
            now = time.monotonic()
            if now - reported >= 5:
                print(f"Extracted {count} files / {size} bytes in {now-started:.1f}s", flush=True)
                reported = now
    result = {"status": "PASS", "files": count, "bytes": size,
              "seconds": round(time.monotonic() - started, 2)}
    (destination / ".source-extraction-complete.json").write_text(json.dumps(result), encoding="utf-8")
    print(json.dumps(result), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    extract(args.archive, args.destination)
