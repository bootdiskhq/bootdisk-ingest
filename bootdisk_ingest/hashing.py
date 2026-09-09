"""Compatibility export; new code should import core.hashing directly."""
from .core.hashing import sha256_file

__all__ = ["sha256_file"]
