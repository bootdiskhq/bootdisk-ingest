import hashlib

from .core.hashing import sha256_file
from .core.identity import build_content_identity

def build_disc_content_identity(file_records):
    """Build a deterministic logical identity for the disc contents.

    The identity is based on the actual on-disc relative path and SHA-256
    of every physical file in the global inventory, sorted by path.
    It intentionally does not include local mount paths, timestamps,
    inode data, or the media-image hash.
    """
    return build_content_identity(file_records)
