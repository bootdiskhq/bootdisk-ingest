"""Compatibility inventory helpers for the existing ingest pipeline.

Generic file discovery, hashing, and path lookup live in the source-agnostic
core inventory module. This module preserves the historical dictionary-based
interface used by the existing ingest pipeline.
"""

from .core.inventory import (
    FileInventory,
    FileRecord,
    build_directory_inventory,
)


def build_disc_inventory(disc_root):
    """Build the legacy disc inventory from the generic core inventory.

    The public structure returned by this function is intentionally kept
    unchanged for compatibility with the existing ingest pipeline.

    File discovery, hashing, and deterministic ordering are delegated to the
    source-agnostic core inventory implementation.
    """

    # Observe the files through the generic preservation core.
    records = build_directory_inventory(disc_root)

    # Convert FileRecord objects back to the historical dictionary format.
    # Existing callers can therefore continue to operate unchanged while the
    # underlying implementation is migrated toward the core model.
    files = [
        {
            "path": record.path,
            "size": record.size,
            "sha256": record.sha256,
        }
        for record in records
    ]

    # Preserve the legacy lookup indexes because other parts of the current
    # ingest pipeline still expect them.
    by_path = {
        item["path"]: item
        for item in files
    }

    by_casefold_path = {}

    for item in files:
        key = item["path"].casefold()

        # Preserve the first occurrence if two observed paths differ only by
        # case. This matches the behaviour of the historical implementation.
        if key not in by_casefold_path:
            by_casefold_path[key] = item

    return {
        "files": files,
        "by_path": by_path,
        "by_casefold_path": by_casefold_path,
    }


def get_file_record(disc_inventory, relative_path):
    """Resolve a legacy file reference using the generic core inventory.

    The result deliberately retains the historical dictionary structure used
    by the ingest pipeline. Only the path-resolution mechanism has moved into
    the source-agnostic core.
    """

    if relative_path is None:
        return None

    # Convert existing dictionary records into core FileRecord objects.
    # No files are read and no hashes are recalculated here; this is only a
    # representation change for the purpose of generic path lookup.
    core_records = [
        FileRecord(
            path=item["path"],
            size=item["size"],
            sha256=item["sha256"],
        )
        for item in disc_inventory["files"]
    ]

    inventory = FileInventory.from_records(core_records)

    # Exact matching takes precedence inside FileInventory. A case-insensitive
    # match is only used as a fallback and is explicitly reported.
    record, matched_case_insensitively = inventory.find(relative_path)

    if record is None:
        return {
            "path": relative_path,
            "exists": False,
        }

    result = {
        "path": relative_path,
        "exists": True,
        "is_file": True,
        "size": record.size,
        "sha256": record.sha256,
    }

    # Keep the path supplied by the source metadata intact. If the filesystem
    # uses different casing, record the observed path separately rather than
    # silently correcting the source.
    if matched_case_insensitively:
        result["resolved_path"] = record.path
        result["path_case_mismatch"] = True

    return result

def get_folder_records(disc_inventory, folder):
    """Resolve a legacy folder reference using the generic core inventory.

    The result remains in the historical dictionary format expected by the
    existing ingest pipeline. Folder matching itself is delegated to the
    source-agnostic FileInventory implementation.
    """

    if not folder:
        return []

    # Convert legacy dictionary records into FileRecord objects without
    # touching the filesystem or recalculating preservation data.
    core_records = [
        FileRecord(
            path=item["path"],
            size=item["size"],
            sha256=item["sha256"],
        )
        for item in disc_inventory["files"]
    ]

    inventory = FileInventory.from_records(core_records)

    matching_records = inventory.find_folder(folder)

    # Convert the core records back to the historical dictionary shape so
    # existing callers remain completely unchanged.
    return [
        {
            "path": record.path,
            "size": record.size,
            "sha256": record.sha256,
        }
        for record in matching_records
    ]
