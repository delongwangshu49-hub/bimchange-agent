"""Copy explicitly allowlisted changes for review; never stages or uploads."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args], cwd=ROOT
    )


def prepare(output):
    output = output.resolve()
    if output.exists():
        raise FileExistsError("Choose a fresh review-output directory")
    # Keep generated review packages outside the repository to avoid recursive input.
    if output == ROOT or ROOT in output.parents:
        raise ValueError("Choose an output directory outside the Git worktree")
    staged_before = git("diff", "--cached", "--binary")
    tracked = git("diff", "--name-only", "-z").decode().split("\0")
    untracked = git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0")
    paths = sorted(set(filter(None, tracked + untracked)))
    rules = [line.strip() for line in (ROOT / "packaging/release-source-allowlist.txt")
             .read_text().splitlines() if line.strip() and not line.startswith("#")]

    def allowed(path):
        return any(path.startswith(rule) if rule.endswith("/") else path == rule for rule in rules)

    selected, excluded = [], []
    for path in paths:
        (selected if allowed(path) else excluded).append(path)
    forbidden = {".ifc", ".rvt", ".glb", ".exe", ".dll", ".zip", ".pyd"}
    for path in selected:
        resolved = (ROOT / path).resolve()
        resolved.relative_to(ROOT)
        if not resolved.is_file() or resolved.suffix.lower() in forbidden or ".env" in resolved.name:
            raise ValueError(f"Disallowed payload: {path}")
        if "held_out" in Path(path).parts:
            raise ValueError("Frozen held-out contents must not enter a changed-file overlay")
    output.mkdir(parents=True)
    records = []
    for path in selected:
        source, destination = ROOT / path, output / "source-overlay" / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"Copy verification failed: {path}")
        records.append({"path": path, "bytes": source.stat().st_size, "sha256": digest})
    # A diff of selected tracked files aids review; new files are in the overlay.
    selected_tracked = [path for path in selected if path in tracked]
    patch = git("diff", "--binary", "--", *selected_tracked) if selected_tracked else b""
    (output / "tracked-changes.patch").write_bytes(patch)
    staged_after = git("diff", "--cached", "--binary")
    if staged_after != staged_before:
        raise RuntimeError("Git index changed during preparation; investigate before proceeding")
    manifest = {"version": "1.0.0", "status": "LOCAL_REVIEW_ONLY_NOT_UPLOAD_AUTHORIZATION",
                "base_commit": git("rev-parse", "HEAD").decode().strip(),
                "source_files": records, "excluded_worktree_paths": excluded,
                "git_index_unchanged": True, "remote_writes": 0,
                "binary_assets_included": False,
                "note": "Changed-file overlay, not a full checkout; preserve existing historical files."}
    (output / "upload-review-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "START-HERE.md").write_text(
        "# 1.0.0 本地 GitHub 更新准备\n\n"
        "此目录仅供审核，不是上传授权，也不是完整源码仓库。\n\n"
        "- source-overlay：明确白名单内的新文件/修改文件，逐项核对后才可应用。\n"
        "- tracked-changes.patch：已跟踪文件的差异；新增文件见 overlay。\n"
        "- upload-review-manifest.json：文件摘要、基线提交及明确排除的工作树内容。\n"
        "- 未包含安装器、便携 ZIP、私有 IFC/GLB/截图、凭据或冻结留出数据。\n"
        "- 不执行 git add/commit/tag/push；既有历史资源不删除、不覆盖。\n\n"
        "公开二进制许可证与最终安装验收仍未闭环；详见 overlay 内的发布检查清单。\n",
        encoding="utf-8")
    return {"selected_files": len(records), "excluded_files": len(excluded),
            "git_index_unchanged": True, "output": str(output)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    print(json.dumps(prepare(parser.parse_args().output), indent=2))
