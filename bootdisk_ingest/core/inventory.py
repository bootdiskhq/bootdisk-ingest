"""Source-agnostic file inventory models and helpers.

The inventory layer records files as they are observed. It deliberately
contains no knowledge about publications, optical media, K-CD, or software
catalog metadata.
"""

from dataclasses import dataclass
from pathlib import Path

from .hashing import sha256_file


@dataclass(slots=True, frozen=True)
class FileRecord:
    """A preserved observation of a single file.

    The path is stored relative to the inventory root so that the record does
    not depend on where the source happened to be mounted or copied locally.
    """

    path: str
    size: int
    sha256: str

@dataclass(slots=True)

class FileInventory:
    """Indexed collection of preserved file observations.

    The inventory keeps the original FileRecord objects while also building
    lookup indexes for exact and case-insensitive path resolution.

    Case-insensitive lookup is intentionally treated as a fallback. Exact path
    matches always take precedence so that preservation does not collapse
    distinct filesystem paths unnecessarily.
    """

    records: list[FileRecord]
    by_path: dict[str, FileRecord]
    by_casefold_path: dict[str, FileRecord]

    @classmethod
    def from_records(cls, records):
        """Create an indexed inventory from FileRecord objects."""

        records = list(records)

        # Exact-path lookup preserves the path exactly as observed.
        by_path = {
            record.path: record
            for record in records
        }

        by_casefold_path = {}

        for record in records:
            key = record.path.casefold()

            # Preserve the first occurrence if multiple observed paths differ
            # only by case. This mirrors the behaviour of the legacy inventory.
            if key not in by_casefold_path:
                by_casefold_path[key] = record

        return cls(
            records=records,
            by_path=by_path,
            by_casefold_path=by_casefold_path,
        )
    def find(self, relative_path):
        """Find a file by path, with case-insensitive fallback.

        Exact matches always take precedence. If only a case-insensitive match
        exists, the matching FileRecord is returned together with a flag showing
        that fallback resolution was required.

        Returning the mismatch information separately allows callers to preserve
        both the source-provided path and the path actually observed.
        """

        if relative_path is None:
            return None, False

        # Prefer the exact observed path whenever possible.
        record = self.by_path.get(relative_path)

        if record is not None:
            return record, False

        # Historical metadata may refer to the correct file using different
        # casing. Resolve that path without silently changing the source value.
        record = self.by_casefold_path.get(
            relative_path.casefold()
        )

        if record is not None:
            return record, True

        return None, False

    def find_folder(self, folder):
        """Find records belonging to a folder, with case-insensitive fallback.

        Exact folder matching is preferred. Case-insensitive matching is used only
        when no exact matches exist, preserving the behaviour of the historical
        Bootdisk inventory implementation.
        """

        if not folder:
            return []

        exact_prefix = folder.rstrip("/") + "/"

        # Prefer paths exactly matching the casing supplied by the source.
        exact_matches = [
            record
            for record in self.records
            if (
                record.path == folder
                or record.path.startswith(exact_prefix)
            )
        ]

        if exact_matches:
            return exact_matches

        # Historical metadata may refer to a valid folder using casing that differs
        # from the filesystem. Fall back without altering the observed FileRecord
        # paths themselves.
        folded_folder = folder.casefold()
        folded_prefix = folded_folder.rstrip("/") + "/"

        return [
            record
            for record in self.records
            if (
                record.path.casefold() == folded_folder
                or record.path.casefold().startswith(folded_prefix)
            )
        ]

def build_directory_inventory(root):
    """Build a deterministic inventory of all files below a directory.

    This function treats the directory purely as a collection of files. It
    does not make assumptions about whether the directory represents a
    mounted CD-ROM, an extracted archive, a floppy image, or another source.

    The returned FileRecord objects contain only observations needed by the
    preservation layer: relative path, file size, and SHA-256 digest.
    """

    root = Path(root)
    records = []

    """Discover files first, then sort them by their relative source path.

    The case-insensitive sort order intentionally matches the historical
    Bootdisk inventory behaviour. Keeping this stable avoids changing
    manifest ordering merely because the implementation was refactored.
    """
    paths = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix().lower(),
    )

    for path in paths:
        records.append(
            FileRecord(
                # Never preserve the machine-specific absolute path. The
                # relative POSIX form gives us a portable source path.
                path=path.relative_to(root).as_posix(),
                size=path.stat().st_size,
                sha256=sha256_file(path),
            )
        )

    return records
