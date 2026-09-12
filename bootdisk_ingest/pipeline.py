"""Application orchestration; this module deliberately selects the K-CD adapter.

Core operations remain reusable without this manifest contract. A future source
adapter must choose its own projection rather than imitate a magazine disc.
"""
from pathlib import Path
from .adapters.kcd.parser import parse_disc
from .inventory import build_inventory, get_file_record
from .adapters.kcd.director import parse_director_disc, validate_director
from .iso9660 import inspect_iso9660
from .media import build_media_metadata
from .stats import build_statistics
from .validation import build_validation


def ingest_kcd(source_root, *, image=None, generated_at=None):
    """Observe stable, externally preserved source files without modifying them.

    The optional image is independent evidence: hashing it does not establish
    that the supplied directory was extracted from it. Keep both inputs stable.
    """
    source_root = Path(source_root).expanduser().resolve()
    if image is not None and not Path(image).expanduser().is_file():
        raise ValueError("The explicitly supplied image must be an existing file")
    inventory = build_inventory(source_root)
    has_dtx = get_file_record(inventory, "K.DTX")["exists"]
    parser = parse_disc if has_dtx else parse_director_disc
    manifest = parser(source_root, inventory, generated_at=generated_at)
    manifest["media"] = build_media_metadata(image)
    manifest["disc"]["filesystem"] = inspect_iso9660(image)
    manifest["file_inventory"] = inventory["files"]
    manifest["statistics"] = build_statistics(manifest["entries"], inventory)
    validator = build_validation if has_dtx else validate_director
    manifest["validation"] = validator(manifest["entries"])
    return manifest
