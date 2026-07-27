from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from product_paths import PRODUCT_ID  # noqa: E402

EXCLUDED_PARTS = {
    ".git",
    ".github",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "Data",
    "Exports",
    "Support",
}
EXCLUDED_NAMES = {"security.json", "state.json", ".migration-complete.json"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def included_files(root: Path) -> list[Path]:
    rows: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.name in EXCLUDED_NAMES or path.suffix in {".pyc", ".pyo"}:
            continue
        rows.append(path)
    return sorted(rows, key=lambda item: item.relative_to(root).as_posix())


def build(destination: Path, *, version: str, build_id: str) -> dict[str, object]:
    destination = destination.resolve()
    stage = destination / f"CSRN-Production-Suite-{version}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    for source in included_files(ROOT):
        relative = source.relative_to(ROOT)
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    files = []
    for path in included_files(stage):
        relative = path.relative_to(stage).as_posix()
        files.append({"path": relative, "size": path.stat().st_size, "sha256": sha256(path)})
    manifest = {
        "schema": 1,
        "product_id": PRODUCT_ID,
        "version": version,
        "build": build_id,
        "created_at": int(time.time()),
        "files": files,
        "installer": {
            "windows_script": "packaging/windows/csrn-production-suite.iss",
            "user_data_outside_binaries": True,
        },
    }
    (stage / "release.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    archive_path = destination / f"CSRN-Production-Suite-{version}.zip"
    if archive_path.exists():
        archive_path.unlink()
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(stage.parent).as_posix())
    return {"stage": str(stage), "archive": str(archive_path), "files": len(files), "manifest": manifest}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a hash-manifested CSRN release package.")
    parser.add_argument("--destination", default="dist-release")
    parser.add_argument("--version", default=(ROOT / "VERSION.txt").read_text(encoding="utf-8").strip())
    parser.add_argument("--build", default="local-release-build")
    args = parser.parse_args()
    result = build(ROOT / args.destination, version=args.version, build_id=args.build)
    print(json.dumps({key: value for key, value in result.items() if key != "manifest"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
