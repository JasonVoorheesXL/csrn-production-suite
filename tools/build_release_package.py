from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from product_paths import PRODUCT_ID  # noqa: E402
from tools.dev_workflow import (  # noqa: E402
    runtime_identity,
    version_file_token,
)


EXCLUDED_PARTS = {
    ".git",
    ".github",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "Data",
    "Exports",
    "Support",
    "dist-release",
}
EXCLUDED_NAMES = {"security.json", "state.json", ".migration-complete.json"}
SAFE_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ZIP_MINIMUM_EPOCH = 315532800  # 1980-01-01 UTC


class BuildError(RuntimeError):
    """Raised when a reproducible release package cannot be built safely."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
    )
    return result.stdout


def included_files(root: Path) -> list[Path]:
    rows: list[Path] = []
    for encoded in git_output(root, "ls-files", "-z").split(b"\0"):
        if not encoded:
            continue
        relative = Path(os.fsdecode(encoded))
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if relative.name in EXCLUDED_NAMES or relative.suffix in {".pyc", ".pyo"}:
            continue
        source = root / relative
        if source.is_file():
            rows.append(source)
    return sorted(rows, key=lambda item: item.relative_to(root).as_posix())


def require_clean_tracked_tree(root: Path) -> None:
    status = git_output(
        root,
        "status",
        "--porcelain",
        "--untracked-files=no",
    ).decode(errors="replace").strip()
    if status:
        raise BuildError(
            "Tracked files are modified. Commit and validate the exact source "
            "before building a release."
        )


def committed_file_bytes(root: Path, relative: Path) -> bytes:
    return git_output(root, "show", f"HEAD:{relative.as_posix()}")


def source_date_epoch(root: Path) -> int:
    override = os.environ.get("SOURCE_DATE_EPOCH")
    if override:
        try:
            return int(override)
        except ValueError as exc:
            raise BuildError("SOURCE_DATE_EPOCH must be an integer.") from exc
    return int(git_output(root, "log", "-1", "--format=%ct").decode().strip())


def zip_timestamp(epoch: int) -> tuple[int, int, int, int, int, int]:
    return time.gmtime(max(epoch, ZIP_MINIMUM_EPOCH))[:6]


def validate_token(label: str, value: str) -> None:
    if not SAFE_TOKEN.fullmatch(value):
        raise BuildError(
            f"{label} must contain only letters, numbers, dots, underscores, "
            "and hyphens."
        )


def write_archive(
    stage: Path,
    archive_path: Path,
    *,
    epoch: int,
) -> None:
    timestamp = zip_timestamp(epoch)
    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(
            (item for item in stage.rglob("*") if item.is_file()),
            key=lambda item: item.relative_to(stage).as_posix(),
        ):
            relative = path.relative_to(stage).as_posix()
            info = zipfile.ZipInfo(f"{stage.name}/{relative}", timestamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def build(
    destination: Path,
    *,
    version: str,
    build_id: str,
    root: Path = ROOT,
    epoch: int | None = None,
) -> dict[str, object]:
    validate_token("Version", version)
    validate_token("Build", build_id)
    root = root.resolve()
    destination = destination.resolve()
    require_clean_tracked_tree(root)
    source_commit = git_output(root, "rev-parse", "HEAD").decode().strip()
    destination.mkdir(parents=True, exist_ok=True)
    stage = destination / f"CSRN-Production-Suite-{version}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()

    files: list[dict[str, object]] = []
    for source in included_files(root):
        relative = source.relative_to(root)
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(committed_file_bytes(root, relative))
        files.append(
            {
                "path": relative.as_posix(),
                "size": target.stat().st_size,
                "sha256": sha256(target),
            }
        )

    effective_epoch = source_date_epoch(root) if epoch is None else epoch
    manifest = {
        "schema": 2,
        "product_id": PRODUCT_ID,
        "version": version,
        "build": build_id,
        "source_commit": source_commit,
        "source_date_epoch": effective_epoch,
        "files": files,
        "installer": {
            "windows_script": "packaging/windows/csrn-production-suite.iss",
            "user_data_outside_binaries": True,
        },
    }
    (stage / "release.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    archive_path = destination / f"CSRN-Production-Suite-{version}.zip"
    if archive_path.exists():
        archive_path.unlink()
    write_archive(stage, archive_path, epoch=effective_epoch)
    return {
        "stage": str(stage),
        "archive": str(archive_path),
        "archive_sha256": sha256(archive_path),
        "files": len(files),
        "manifest": manifest,
    }


def main() -> int:
    identity = runtime_identity(ROOT / "app.py")
    default_version = version_file_token(
        (ROOT / "VERSION.txt").read_text(encoding="utf-8")
    )
    parser = argparse.ArgumentParser(
        description="Build a deterministic, hash-manifested CSRN release package."
    )
    parser.add_argument("--destination", default="dist-release")
    parser.add_argument("--version", default=default_version)
    parser.add_argument("--build", default=identity.build)
    args = parser.parse_args()
    destination = Path(args.destination)
    if not destination.is_absolute():
        destination = ROOT / destination
    try:
        result = build(
            destination,
            version=args.version,
            build_id=args.build,
        )
    except (BuildError, OSError, subprocess.CalledProcessError) as exc:
        print(f"CSRN release build failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "manifest"},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
