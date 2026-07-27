from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Iterable
from urllib.parse import unquote, urlparse


class SocialAssetResolver:
    """Resolve CSRN-managed media references to safe local files.

    Social rendering intentionally does not download arbitrary remote media. Only
    files underneath configured application or customer-data roots are eligible.
    """

    def __init__(
        self,
        *,
        base_dir: Path,
        data_dir: Path,
        asset_upload_dir: Path,
        headshots_dir: Path,
    ) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.data_dir = Path(data_dir).resolve()
        self.asset_upload_dir = Path(asset_upload_dir).resolve()
        self.headshots_dir = Path(headshots_dir).resolve()
        self.allowed_roots = tuple(
            root
            for root in {
                self.base_dir,
                self.data_dir,
                self.asset_upload_dir,
                self.headshots_dir,
            }
            if root.exists() or root.parent.exists()
        )

    @staticmethod
    def _parts(reference: str) -> tuple[str, ...]:
        path = PurePosixPath(unquote(reference.replace("\\", "/")))
        return tuple(part for part in path.parts if part not in {"", "/"})

    @staticmethod
    def _safe_join(root: Path, parts: Iterable[str]) -> Path | None:
        parts = tuple(parts)
        if not parts or any(part in {".", ".."} for part in parts):
            return None
        try:
            candidate = root.joinpath(*parts).resolve()
            candidate.relative_to(root.resolve())
        except (OSError, ValueError):
            return None
        return candidate if candidate.is_file() else None

    def __call__(self, reference: str) -> Path | None:
        reference = str(reference or "").strip()
        if not reference:
            return None
        parsed = urlparse(reference)
        if parsed.scheme or parsed.netloc:
            return None
        parts = self._parts(parsed.path or reference)
        if not parts:
            return None

        first = parts[0].casefold()
        candidates: list[tuple[Path, tuple[str, ...]]] = []
        if first == "static":
            candidates.append((self.base_dir / "static", parts[1:]))
        elif first == "asset-files":
            candidates.append((self.asset_upload_dir, parts[1:]))
        elif first == "roster-headshots":
            candidates.append((self.headshots_dir, parts[1:]))
        elif first == "school-logos" and len(parts) >= 3:
            school_id = parts[1]
            filename_parts = parts[2:]
            candidates.extend(
                [
                    (self.data_dir / "Logos" / school_id, filename_parts),
                    (self.base_dir / "Data" / "Logos" / school_id, filename_parts),
                    (self.base_dir / "static" / "school-logos" / school_id, filename_parts),
                ]
            )
        else:
            candidates.extend(
                [
                    (self.base_dir, parts),
                    (self.data_dir, parts),
                ]
            )

        for root, relative in candidates:
            resolved = self._safe_join(root.resolve(), relative)
            if resolved is None:
                continue
            try:
                if any(resolved.is_relative_to(allowed) for allowed in self.allowed_roots):
                    return resolved
            except (OSError, ValueError):
                continue
        return None
