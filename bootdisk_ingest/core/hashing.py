"""Byte identities are independent of filenames and source context."""
import hashlib
from pathlib import Path


def sha256_file(path, chunk_size=1024 * 1024):
    """Stream bytes without loading historical images into memory."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    path = Path(path)
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()
