from __future__ import annotations

import hashlib
from pathlib import Path


FileCacheSignature = tuple[int, int, bytes]


def file_cache_signature(path: Path) -> FileCacheSignature | None:
    """Return a content-aware signature for a cacheable file.

    Modification timestamps alone are not sufficient on every Windows or synced
    filesystem. Two same-length rewrites can occur inside the filesystem's
    timestamp resolution and otherwise leave an in-memory repository cache
    looking current. Including a compact content digest keeps cache invalidation
    reliable while still avoiding JSON parsing and domain normalization when the
    file has not changed.
    """

    target = Path(path)
    try:
        payload = target.read_bytes()
        stat = target.stat()
    except OSError:
        return None

    digest = hashlib.blake2b(payload, digest_size=16).digest()
    return stat.st_mtime_ns, stat.st_size, digest
