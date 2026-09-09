"""Identity of the exact supplied image bytes, independent of source metadata."""
from pathlib import Path

from .core.hashing import sha256_file


def _guess_format(image_path):
    """Return a filename-extension hint, not a verified media format."""
    suffix = image_path.suffix.lower()

    if suffix == ".iso":
        return "iso"

    if suffix == ".img":
        return "img"

    if suffix == ".bin":
        return "bin"

    if suffix == ".cue":
        return "cue"

    if suffix:
        return suffix.lstrip(".")

    return "unknown"


def build_media_metadata(image_path):
    if image_path is None:
        return {
            "available": False,
        }

    image_path = Path(image_path).expanduser().resolve()

    if not image_path.exists():
        return {
            "available": False,
            "error": "image_not_found",
        }

    if not image_path.is_file():
        return {
            "available": False,
            "error": "image_not_file",
        }

    sha256 = sha256_file(image_path)

    return {
        "available": True,
        "format": _guess_format(image_path),
        "size": image_path.stat().st_size,
        "sha256": sha256,
        "media_id": f"sha256:{sha256}",
    }
