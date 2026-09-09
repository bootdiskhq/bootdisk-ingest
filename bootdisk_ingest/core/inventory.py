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

            # Keep a representative for the compatibility index. find() rejects
            # ambiguous fallback instead of treating this representative as evidence.
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
            matches = [item for item in self.records if item.path.casefold() == relative_path.casefold()]
            if len(matches) > 1:
                raise ValueError(f"Ambiguous case-insensitive path: {relative_path}")
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

        matches = [
            record
            for record in self.records
            if (
                record.path.casefold() == folded_folder
                or record.path.casefold().startswith(folded_prefix)
            )
        ]

        # A fallback must not merge distinct observed directories into one entry.
        depth = len(folder.rstrip("/").split("/"))
        observed_folders = {"/".join(record.path.split("/")[:depth]) for record in matches}
        if len(observed_folders) > 1:
            raise ValueError(f"Ambiguous case-insensitive folder: {folder}")
        return matches

def build_directory_inventory(root):
    """Build a deterministic inventory of all files below a directory.

    This function treats the directory purely as a collection of files. It
    does not make assumptions about whether the directory represents a
    mounted CD-ROM, an extracted archive, a floppy image, or another source.

    The returned FileRecord objects contain only observations needed by the
    preservation layer: relative path, file size, and SHA-256 digest.
    """

    root = Path(root)
    if not root.is_dir():
        raise ValueError("Inventory root must be an existing directory")
    records = []
    paths = []
    # Explicit traversal propagates access errors. Silently skipping unreadable
    # directories would produce a plausible but incomplete preservation record.
    def discover(directory):
        import os
        import stat
        with os.scandir(directory) as children:
            for child in children:
                mode = child.stat(follow_symlinks=False).st_mode
                if stat.S_ISLNK(mode):
                    raise ValueError(f"Symbolic links are not supported: {child.path}")
                if stat.S_ISDIR(mode):
                    discover(Path(child.path))
                elif stat.S_ISREG(mode):
                    paths.append(Path(child.path))
                else:
                    raise ValueError(f"Special files are not supported: {child.path}")

    discover(root)
    # Preserve legacy ordering, with an exact-path tie-break for case collisions.
    paths.sort(key=lambda path: (
        path.relative_to(root).as_posix().lower(),
        path.relative_to(root).as_posix(),
    ))
    for path in paths:
        before = path.stat()
        digest = sha256_file(path)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (
            after.st_size, after.st_mtime_ns, after.st_ino
        ):
            raise ValueError(f"Source changed while hashing: {path}")
        records.append(FileRecord(path.relative_to(root).as_posix(), before.st_size, digest))
    return records
